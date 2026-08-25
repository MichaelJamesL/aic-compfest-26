import os
from types import SimpleNamespace

import pytest

from src import knowledge
from src.schemas import AnalysisRequest, Asset, BusinessContext, Document, Tier


class FakeConnection:
    def __init__(self, rows=(), chunks=()):
        self.calls = []
        self.rows = list(rows)
        self.committed_chunks = list(chunks)
        self.pending_chunks = list(chunks)
        self.fail_on_insert = False
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        normalized = " ".join(sql.split())
        if normalized.startswith("SELECT atttypmod"):
            # init_schema's dimension check — a matching column, so no drop.
            return SimpleNamespace(fetchall=lambda: [(knowledge.DIM,)])
        if normalized.startswith("DELETE FROM doc_chunk"):
            self.pending_chunks = [
                chunk for chunk in self.pending_chunks
                if not (chunk[0] == params[0] and chunk[1] == params[1])
            ]
        elif normalized.startswith("INSERT INTO doc_chunk"):
            if self.fail_on_insert:
                raise RuntimeError("insert failed")
            self.pending_chunks.append((params[2], params[0]))
        return SimpleNamespace(fetchall=lambda: self.rows)

    def commit(self):
        self.commits += 1
        self.committed_chunks = list(self.pending_chunks)

    def rollback(self):
        self.rollbacks += 1
        self.pending_chunks = list(self.committed_chunks)

    def close(self):
        self.closed = True


def test_init_schema_upgrades_existing_volume_without_drop(monkeypatch):
    conn = FakeConnection()
    knowledge.init_schema(conn)
    sql = " ".join(" ".join(call[0].split()) for call in conn.calls)
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    assert "ALTER TABLE doc_chunk ADD COLUMN IF NOT EXISTS factory_id TEXT" in sql
    assert "CREATE INDEX IF NOT EXISTS doc_chunk_embedding_idx" in sql
    assert "DROP" not in sql


def test_ingest_replaces_document_and_rolls_back_on_insert_failure(monkeypatch):
    conn = FakeConnection(chunks=[("doc-1", "factory-a")])
    monkeypatch.setattr(knowledge, "_split_chunks", lambda text: [text])
    monkeypatch.setattr(knowledge, "embed", lambda texts: [[0.1, 0.2]])
    document = Document(id="doc-1", title="SOP", text="new", factory_id="factory-a")

    assert knowledge.ingest(document, asset_id="asset-a", conn=conn) == 1
    delete = [call for call in conn.calls if call[0].startswith("DELETE")]
    insert = [call for call in conn.calls if call[0].lstrip().startswith("INSERT")]
    assert delete and delete[0][1] == ("doc-1", "factory-a")
    assert insert[0][1][0] == "factory-a"
    assert conn.commits == 2  # schema bootstrap, then the replacement transaction

    conn.fail_on_insert = True
    with pytest.raises(RuntimeError, match="insert failed"):
        knowledge.ingest(document, factory_id="factory-a", conn=conn)
    assert conn.rollbacks == 1
    assert conn.committed_chunks == [("doc-1", "factory-a")]


def test_ingest_deletes_only_matching_document_and_factory(monkeypatch):
    conn = FakeConnection(chunks=[("doc-1", "factory-a"), ("doc-1", "factory-b")])
    monkeypatch.setattr(knowledge, "_split_chunks", lambda text: [text])
    monkeypatch.setattr(knowledge, "embed", lambda texts: [[0.1, 0.2]])
    document = Document(id="doc-1", title="SOP", text="new", factory_id="factory-a")

    knowledge.ingest(document, conn=conn)

    assert conn.committed_chunks == [("doc-1", "factory-b"), ("doc-1", "factory-a")]


def test_search_scopes_global_and_asset_chunks_to_factory(monkeypatch):
    conn = FakeConnection([("SOP", "sop", "text", 4, 0.9)])
    monkeypatch.setattr(knowledge, "embed", lambda texts: [[0.1, 0.2]])

    result = knowledge.search("pump", "asset-a", "factory-a", conn=conn)

    assert result[0].similarity == 0.9
    search = next(call for call in conn.calls if call[0].lstrip().startswith("SELECT doc_title"))
    assert search[1][1:3] == ("factory-a", "asset-a")


def test_context_passes_factory_id_to_retrieval(monkeypatch):
    captured = {}
    monkeypatch.setattr(knowledge, "search", lambda *args, **kwargs: captured.update(args=args, kwargs=kwargs) or [])
    request = AnalysisRequest(
        factory_id="factory-a",
        tier=Tier.STARTER,
        asset=Asset(id="asset-a", name="Pump", type="pump"),
        business=BusinessContext(),
    )

    from src.context import select_context
    select_context(request, budget_tokens=100)
    assert captured["args"][1:3] == ("asset-a", "factory-a")


@pytest.mark.skipif(
    not (os.getenv("RUN_LIVE_PGVECTOR") and os.getenv("AIENGINE_DATABASE_URL")),
    reason="set RUN_LIVE_PGVECTOR=1 and AIENGINE_DATABASE_URL for live pgvector smoke",
)
def test_live_pgvector_ingest_and_search():
    document = Document(id="live-smoke", title="Live SOP", text="Pump bearing inspection", factory_id="live-factory")
    knowledge.init_schema()
    assert knowledge.ingest(document) == 1
    assert knowledge.search("bearing inspection", None, "live-factory", k=1)[0].title == "Live SOP"
