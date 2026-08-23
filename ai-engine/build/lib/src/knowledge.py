"""pgvector knowledge base: ingest documents, search chunks by cosine similarity."""
from __future__ import annotations

import psycopg
import numpy as np
from pgvector.psycopg import register_vector

from .config import DATABASE_URL
from .embed import embed
from .schemas import ContextDoc, Document

WINDOW_SIZE = 800
OVERLAP = 100


def connect() -> psycopg.Connection:
    conn = psycopg.connect(DATABASE_URL)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.commit()
    register_vector(conn)
    return conn


def init_schema(conn: psycopg.Connection | None = None) -> None:
    close = conn is None
    conn = conn or connect()
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS doc_chunk (
          id BIGSERIAL PRIMARY KEY,
          factory_id TEXT,
          asset_id TEXT,
          doc_id TEXT, doc_title TEXT, kind TEXT,
          chunk_index INT, text TEXT,
          embedding VECTOR(1024)
        )
        """
    )
    # CREATE TABLE does not upgrade a table on an existing Docker volume.
    conn.execute("ALTER TABLE doc_chunk ADD COLUMN IF NOT EXISTS factory_id TEXT")
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS doc_chunk_embedding_idx
        ON doc_chunk USING hnsw (embedding vector_cosine_ops)
        """
    )
    conn.commit()
    if close:
        conn.close()


def _split_chunks(text: str) -> list[str]:
    """Split text into ~800-char windows with ~100-char overlap at headings."""
    lines = text.splitlines()
    sections: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        stripped = line.strip()
        is_heading = (
            len(stripped) < 80
            and stripped
            and any(s in stripped for s in ("#", "Section", "section"))
        ) or (len(stripped) <= 40 and stripped and not stripped.endswith("."))
        if is_heading and current:
            sections.append(current)
            current = []
        current.append(line)
    if current:
        sections.append(current)

    chunks: list[str] = []
    pile = ""
    for section in sections:
        block = "\n".join(section).strip()
        if not block:
            continue
        if pile and len(pile) + len(block) > WINDOW_SIZE:
            chunks.append(pile)
            pile = ""
        while len(block) > WINDOW_SIZE:
            chunks.append(block[:WINDOW_SIZE])
            block = block[WINDOW_SIZE - OVERLAP:]
        pile = (pile + "\n" + block).strip() if pile else block
    if pile:
        chunks.append(pile)
    return chunks


def ingest(
    document: Document,
    asset_id: str | None = None,
    factory_id: str | None = None,
    conn: psycopg.Connection | None = None,
) -> int:
    close = conn is None
    conn = conn or connect()
    try:
        init_schema(conn)
        chunks = _split_chunks(document.text)
        vectors = embed(chunks)
        if len(vectors) != len(chunks):
            raise ValueError("embedding count does not match chunk count")
        scoped_factory_id = factory_id or document.factory_id
        # Prepare embeddings before deleting the old version, then replace all
        # chunks in one transaction so a failed reindex cannot claim readiness.
        conn.execute(
            "DELETE FROM doc_chunk WHERE doc_id = %s AND factory_id = %s",
            (document.id, scoped_factory_id),
        )
        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            conn.execute(
                """
                INSERT INTO doc_chunk
                    (factory_id, asset_id, doc_id, doc_title, kind, chunk_index, text, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (scoped_factory_id, asset_id, document.id, document.title, document.kind, i, chunk, vector),
            )
        conn.commit()
        return len(chunks)
    except Exception:
        conn.rollback()
        raise
    finally:
        if close:
            conn.close()


def search(
    query: str,
    asset_id: str | None,
    factory_id: str,
    k: int = 5,
    conn: psycopg.Connection | None = None,
) -> list[ContextDoc]:
    close = conn is None
    conn = conn or connect()
    init_schema(conn)
    # pgvector adapts numpy arrays, not plain lists.
    vector = np.asarray(embed([query])[0], dtype=np.float32)
    rows = conn.execute(
        """
        SELECT doc_title, kind, text, id, 1 - (embedding <=> %s) AS similarity
        FROM doc_chunk
        WHERE factory_id = %s AND (asset_id = %s OR asset_id IS NULL)
        ORDER BY embedding <=> %s
        LIMIT %s
        """,
        (vector, factory_id, asset_id, vector, k),
    ).fetchall()
    if close:
        conn.close()
    return [
        ContextDoc(title=row[0], kind=row[1], text=row[2], chunk_id=row[3], similarity=row[4])
        for row in rows
    ]
