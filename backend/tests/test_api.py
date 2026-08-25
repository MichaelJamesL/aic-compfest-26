import os
import pytest
import base64
import sys
import types
import io
import csv as csv_module
# The suite must never reach DeepSeek: a .env with AI_ENGINE_ENABLED=true would
# otherwise make every verification depend on the network.
os.environ["AI_ENGINE_ENABLED"] = "false"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["STORAGE_PATH"] = "/tmp/aic-backend-test"
from fastapi.testclient import TestClient
from app.main import app
from app.documents.service import factory_storage_key, safe_storage_path, MAX_PDF_PAGES, MAX_PDF_TEXT, extract_text, check_file
from app import services as _svc
from app.analysis import service as analysis_service
from app import models, services
from app.db import SessionLocal

def test_starter_flow():
    with TestClient(app) as client:
        assert client.get("/health/live").json()["status"] == "ok"
        assert client.get("/health/ready").json() == {"status": "ready", "database": "ok", "storage": "ok"}
        asset = client.post("/api/v1/assets", json={"name":"Pump 1","asset_type":"pump"}).json()
        aid = asset["id"]
        client.put(f"/api/v1/assets/{aid}/condition", json={"condition":"vibration increased"})
        result = client.post(f"/api/v1/assets/{aid}/analyses", json={"manual_condition":"vibration increased"}).json()
        assert result["status"] == "succeeded"
        wo = client.post(f"/api/v1/analyses/{result['id']}/work-orders").json()
        assert wo["status"] == "draft"
        assert client.get("/api/v1/dashboard/summary").json()["assets"] >= 1


def test_real_ai_engine_path_uses_testmodel_without_network(monkeypatch):
    pytest.importorskip("pydantic_ai")
    ai_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ai-engine"))
    if ai_root not in sys.path:
        sys.path.insert(0, ai_root)
    from pydantic_ai.models.test import TestModel
    from src import MaintenanceEngine
    from src import context as engine_context
    monkeypatch.setattr(engine_context.knowledge, "search", lambda *args, **kwargs: [])
    engine = MaintenanceEngine(model=TestModel())
    monkeypatch.setattr(analysis_service, "engine_factory", lambda settings: engine)
    with TestClient(app) as client:
        asset = client.post("/api/v1/assets", json={"name": "Real engine integration"}).json()
        response = client.post(f"/api/v1/assets/{asset['id']}/analyses", json={"manual_condition": "vibration"})
        assert response.status_code == 201
        assert response.json()["status"] == "succeeded"
        assert response.json()["engine_mode"] == "ai_engine"


def test_analysis_disclosure_is_snapshot_derived_and_flags_are_respected(monkeypatch):
    with TestClient(app) as client:
        asset = client.post("/api/v1/assets", json={"name": "Disclosure"}).json()
        response = client.post(
            f"/api/v1/assets/{asset['id']}/analyses",
            headers={"X-Request-ID": "disclosure-request"},
            json={"include_history": False, "include_business_context": False},
        )
        assert response.status_code == 201
        disclosure = response.json()["input_disclosure"]
        assert disclosure["available"] == []
        assert set(disclosure["missing"]) == {"readings", "history", "business_context", "manual_condition", "qc_images"}
        assert {item["token"] for item in disclosure["limitations"]} == {"readings", "history", "business_context", "manual_condition", "qc_images"}
        fetched = client.get(f"/api/v1/analyses/{response.json()['id']}").json()
        assert fetched["input_disclosure"] == disclosure
        assert fetched["request_snapshot"]["history"] == []


def test_analysis_tier_and_response_contract_are_consistent():
    with TestClient(app) as client:
        asset = client.post("/api/v1/assets", json={"name": "Contract"}).json()
        invalid = client.post(f"/api/v1/assets/{asset['id']}/analyses", json={"tier": "enterprise"})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"

        created = client.post(f"/api/v1/assets/{asset['id']}/analyses", json={"tier": "standard"})
        fetched = client.get(f"/api/v1/analyses/{created.json()['id']}")
        for field in ("status", "error", "error_code", "health_score", "priority", "input_disclosure"):
            assert created.json()[field] == fetched.json()[field]


def test_request_id_is_preserved_when_valid_and_bounded_when_long():
    with TestClient(app) as client:
        valid = "request-id-123"
        assert client.get("/health/live", headers={"X-Request-ID": valid}).headers["x-request-id"] == valid
        long_id = "x" * 100
        response = client.get("/health/live", headers={"X-Request-ID": long_id})
        assert response.headers["x-request-id"] == long_id[:36]


def test_audit_events_cover_creation_analysis_failure_and_work_order_evidence(monkeypatch):
    class Broken:
        mode = "test"
        def analyze(self, request):
            raise RuntimeError("boom")
    with TestClient(app) as client:
        asset_response = client.post("/api/v1/assets", headers={"X-Request-ID": "asset-audit"}, json={"name": "Audited"})
        asset = asset_response.json()
        monkeypatch.setattr(analysis_service, "engine_factory", lambda settings: Broken())
        failed = client.post(f"/api/v1/assets/{asset['id']}/analyses", headers={"X-Request-ID": "analysis-fail"}, json={})
        assert failed.json()["status"] == "failed"
        monkeypatch.undo()
        run = client.post(f"/api/v1/assets/{asset['id']}/analyses", headers={"X-Request-ID": "analysis-success"}, json={}).json()
        wo = client.post(f"/api/v1/analyses/{run['id']}/work-orders", headers={"X-Request-ID": "wo-create"}).json()
        oid = wo["id"]
        for path, headers, request_id in (("submit", {}, "wo-submit"), ("approve", MANAGER, "wo-approve"), ("schedule", {}, "wo-schedule"), ("start", {}, "wo-start")):
            assert client.post(f"/api/v1/work-orders/{oid}/{path}", headers={**headers, "X-Request-ID": request_id}).status_code == 200
        assert client.post(f"/api/v1/work-orders/{oid}/result", headers={**TECHNICIAN, "X-Request-ID": "wo-result"}, json={"work_done": "fixed", "findings": "clear"}).status_code == 200
        assert client.post(f"/api/v1/work-orders/{oid}/verify", headers={"X-Request-ID": "wo-verify"}).status_code == 200
        with SessionLocal() as db:
            events = db.query(models.AuditEvent).filter(models.AuditEvent.resource_id.in_([asset["id"], failed.json()["id"], run["id"], oid])).all()
            by_action = {(event.action, event.request_id) for event in events}
            assert ("asset.created", "asset-audit") in by_action
            assert ("analysis.failed", "analysis-fail") in by_action
            assert ("analysis.completed", "analysis-success") in by_action
            assert ("work_order.status_changed", "wo-submit") in by_action
            assert ("work_order.result_submitted", "wo-result") in by_action
            assert ("work_order.verification_completed", "wo-verify") in by_action


@pytest.mark.parametrize("value", ["../etc", "a/b", "a\\\\b", "", ".", "-bad", "a" * 65])
def testfactory_storage_key_rejects_hostile_input(value):
    with pytest.raises(ValueError):
        factory_storage_key(value)


def test_upload_storage_path_is_contained():
    settings = __import__("app.main", fromlist=["get_settings"]).get_settings()
    assert safe_storage_path(settings, "demo-factory/file.txt").is_relative_to(settings.storage_path.resolve())
    with pytest.raises(ValueError):
        safe_storage_path(settings, "../outside.txt")
    with TestClient(app) as client:
        response = client.post("/api/v1/knowledge/documents", files={"file": ("../../outside.txt", b"safe", "text/plain")})
        assert response.status_code == 201
        with SessionLocal() as db:
            document = db.get(models.Document, response.json()["id"])
            stored = safe_storage_path(settings, document.storage_key)
            assert stored.is_relative_to(settings.storage_path.resolve())

def test_import_and_document():
    with TestClient(app) as client:
        response=client.post("/api/v1/assets/import", files={"file":("assets.csv",b"name,asset_type\nImported,pump\n","text/csv")})
        assert response.json()["imported"] == 1
        doc=client.post("/api/v1/knowledge/documents", files={"file":("sop.txt",b"Lockout procedure","text/plain")}).json()
        assert doc["ingestion_status"] == "pending"
        qc = client.post("/api/v1/knowledge/documents?kind=qc_standard", files={"file": ("qc.txt", b"Tolerance standard", "text/plain")}).json()
        assert qc["kind"] == "qc_standard"
        rejected = client.post("/api/v1/knowledge/documents", files={"file": ("data.xlsx", b"not a document", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert rejected.status_code == 422

def test_pdf_extraction_rejects_malformed_and_keeps_valid_empty_pdf_honest():
    from pypdf import PdfWriter
    output = io.BytesIO(); PdfWriter().add_blank_page(width=72, height=72)
    writer = PdfWriter(); writer.add_blank_page(width=72, height=72); writer.write(output)
    with TestClient(app) as client:
        malformed = client.post("/api/v1/knowledge/documents", files={"file": ("bad.pdf", b"not pdf", "application/pdf")})
        assert malformed.status_code == 422
        empty = client.post("/api/v1/knowledge/documents", files={"file": ("empty.pdf", output.getvalue(), "application/pdf")})
        assert empty.status_code == 201
        with SessionLocal() as db:
            assert db.get(models.Document, empty.json()["id"]).extracted_text == ""
        reindexed = client.post(f"/api/v1/knowledge/documents/{empty.json()['id']}/reindex")
        assert reindexed.json()["ingestion_status"] == "failed"


def test_pdf_limits_are_rejected_before_unbounded_extraction(monkeypatch):
    class ManyPages:
        pages = [object()] * (MAX_PDF_PAGES + 1)
    monkeypatch.setattr("pypdf.PdfReader", lambda *args, **kwargs: ManyPages())
    with pytest.raises(ValueError, match="pdf_too_many_pages"):
        extract_text("large.pdf", "application/pdf", b"pdf")

def test_text_pdf_extraction():
    pdf = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 51>>stream
BT /F1 12 Tf 72 720 Td (Maintenance SOP) Tj ET
endstream endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f
trailer<</Root 1 0 R/Size 6>>
startxref
0
%%EOF"""
    assert "Maintenance SOP" in extract_text("sop.pdf", "application/pdf", pdf)

def test_bulk_history_csv_and_xlsx_are_scoped_and_report_row_errors():
    from openpyxl import Workbook
    with TestClient(app) as client:
        asset = client.post("/api/v1/assets", json={"name": "History", "external_id": "hist-1"}).json()
        csv_data = b"asset_external_id,performed_at,action,findings,parts_used\nhist-1,2026-08-23T10:00:00Z,Repair,clear,bearing,extra\nmissing,2026-08-23T10:00:00Z,Repair,,"
        response = client.post("/api/v1/maintenance-records/import", files={"file": ("history.csv", csv_data, "text/csv")})
        assert response.status_code == 200 and response.json()["imported"] == 1
        assert response.json()["errors"][0]["reason"] == "asset_not_found"
        book = Workbook(); sheet = book.active; sheet.append(["asset_id", "performed_at", "action"]); sheet.append([asset["id"], "2026-08-24T10:00:00Z", "Inspect"])
        output = io.BytesIO(); book.save(output)
        assert client.post("/api/v1/maintenance-records/import", files={"file": ("history.xlsx", output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}).json()["imported"] == 1
        other = client.post("/api/v1/maintenance-records/import", headers={"X-Factory-ID": "other"}, files={"file": ("history.csv", csv_data, "text/csv")}).json()
        assert other["imported"] == 0 and other["errors"][0]["reason"] == "asset_not_found"


def test_bulk_history_external_id_is_idempotent_and_malformed_xlsx_is_enveloped():
    with TestClient(app) as client:
        asset = client.post("/api/v1/assets", json={"name": "Idempotent history"}).json()
        data = b"asset_id,performed_at,action,external_id\n%s,2026-08-23T10:00:00Z,Inspect,h-1\n" % asset["id"].encode()
        first = client.post("/api/v1/maintenance-records/import", files={"file": ("history.csv", data, "text/csv")})
        second = client.post("/api/v1/maintenance-records/import", files={"file": ("history.csv", data, "text/csv")})
        assert first.json()["imported"] == 1
        assert second.json()["imported"] == 0
        assert second.json()["errors"][0]["reason"] == "duplicate_external_id"
        malformed = client.post("/api/v1/maintenance-records/import", files={"file": ("history.xlsx", b"not xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert malformed.status_code == 422
        assert malformed.json()["error"]["code"] == "VALIDATION_ERROR"

def test_sensor_csv_reuses_idempotent_persistence_and_reports_bad_rows():
    with TestClient(app) as client:
        asset = client.post("/api/v1/assets", json={"name": "CSV sensors"}).json()
        data = b"tag,value,unit,recorded_at,external_id\ntemp,42,C,2026-08-23T10:00:00Z,s-1\ntemp,nope,C,2026-08-23T10:01:00Z,s-2"
        first = client.post(f"/api/v1/assets/{asset['id']}/readings/import", files={"file": ("readings.csv", data, "text/csv")}).json()
        second = client.post(f"/api/v1/assets/{asset['id']}/readings/import", files={"file": ("readings.csv", data, "text/csv")}).json()
        assert first["count"] == second["count"] == 1
        assert len(client.get(f"/api/v1/assets/{asset['id']}/readings").json()) == 1


def test_document_reindex_passes_factory_and_reports_failures(monkeypatch):
    captured = {}

    class EngineDocument:
        def __init__(self, **values):
            captured["document"] = values
            self.__dict__.update(values)

    def ingest(document, **kwargs):
        captured["kwargs"] = kwargs
        if len(captured.get("ingested", [])) == 1:
            raise RuntimeError("database unavailable")
        captured.setdefault("ingested", []).append(document.id)
        return 1

    fake_src = types.ModuleType("src")
    fake_src.Document = EngineDocument
    fake_src.knowledge = types.SimpleNamespace(ingest=ingest)
    monkeypatch.setitem(sys.modules, "src", fake_src)

    with TestClient(app) as client:
        first = client.post("/api/v1/knowledge/documents", files={"file": ("sop.txt", b"Pump inspection", "text/plain")}).json()
        response = client.post(f"/api/v1/knowledge/documents/{first['id']}/reindex")
        assert response.status_code == 200
        assert response.json()["ingestion_status"] == "ready"
        assert captured["document"]["factory_id"] == "demo-factory"
        assert captured["kwargs"]["factory_id"] == "demo-factory"

        failed = client.post("/api/v1/knowledge/documents", files={"file": ("failed.txt", b"Failure path", "text/plain")}).json()
        failed_response = client.post(f"/api/v1/knowledge/documents/{failed['id']}/reindex")
        assert failed_response.status_code == 200
        assert failed_response.json()["ingestion_status"] == "failed"
        assert "database unavailable" in failed_response.json()["ingestion_error"]

def test_asset_import_external_id_and_reading_without_id_are_correctly_distinct():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/assets/import",
            files={"file": ("assets.csv", b"name,asset_type,external_id\nA,pump,x-1\nB,pump,x-1\n", "text/csv")},
        )
        assert response.json()["imported"] == 1
        assert response.json()["errors"][0]["reason"] == "duplicate_external_id"

        asset = client.post("/api/v1/assets", json={"name": "Readings"}).json()
        payload = {"tag": "temp", "value": 1, "recorded_at": "2026-08-23T10:00:00Z"}
        first = client.post(f"/api/v1/assets/{asset['id']}/readings", json=payload).json()
        second = client.post(f"/api/v1/assets/{asset['id']}/readings", json=payload).json()
        assert first["id"] != second["id"]


MANAGER = {"X-Demo-User": "demo-manager"}
TECHNICIAN = {"X-Demo-User": "demo-technician"}


def _work_order(client):
    asset = client.post("/api/v1/assets", json={"name": "CNC-02", "asset_type": "cnc-mill"}).json()
    run = client.post(f"/api/v1/assets/{asset['id']}/analyses", json={"manual_condition": "chatter"}).json()
    return client.post(f"/api/v1/analyses/{run['id']}/work-orders").json()


def test_full_work_order_lifecycle():
    """AI proposes, coordinator approves, technician executes.

    Every one of these transitions was unreachable before: nothing targeted
    `approved`, so a work order dead-ended at `pending_approval`.
    """
    with TestClient(app) as client:
        wo = _work_order(client)
        order_id = wo["id"]

        steps = [
            ("submit", {}, "pending_approval"),
            ("approve", MANAGER, "approved"),
            ("schedule", {}, "scheduled"),
            ("start", {}, "in_progress"),
        ]
        for path, headers, expected in steps:
            response = client.post(f"/api/v1/work-orders/{order_id}/{path}", headers=headers)
            assert response.status_code == 200, (path, response.text)
            assert response.json()["status"] == expected

        assert client.post(f"/api/v1/work-orders/{order_id}/complete").status_code == 409


def _roster(client, technicians, production=None):
    client.put("/api/v1/business-context", json={
        "production_schedule": {"work_time": production} if production else None,
        "technicians": technicians,
    })


ALL_DAY = {day: {"start": "00:00:00", "end": "23:30:00"} for day in
           ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")}


def test_work_order_is_proposed_with_a_technician_and_a_slot():
    with TestClient(app) as client:
        _roster(client, [{"name": "Budi", "role": "mekanik", "work_time": ALL_DAY, "occupied_time": {}}])
        wo = _work_order(client)
        assert wo["assigned_technician"] == "Budi"
        assert wo["scheduled_start"] and wo["scheduled_end"]


def test_a_held_slot_is_not_offered_to_the_next_work_order():
    """The whole point: a proposal blocks that technician from the moment it exists."""
    with TestClient(app) as client:
        _roster(client, [{"name": "Budi", "role": "mekanik", "work_time": ALL_DAY, "occupied_time": {}}])
        first = _work_order(client)
        second = _work_order(client)
        assert second["assigned_technician"] == "Budi"
        assert second["scheduled_start"] >= first["scheduled_end"], (first, second)

        # a second technician means the next job runs in parallel, not after
        _roster(client, [
            {"name": "Budi", "role": "mekanik", "work_time": ALL_DAY, "occupied_time": {}},
            {"name": "Sari", "role": "mekanik", "work_time": ALL_DAY, "occupied_time": {}},
        ])
        third = _work_order(client)
        assert third["assigned_technician"] == "Sari"
        assert third["scheduled_start"] < second["scheduled_end"]


def test_standing_busy_blocks_and_shifts_are_respected():
    with TestClient(app) as client:
        # on shift 08:00-17:00, but booked solid until 15:00 every day
        _roster(client, [{
            "name": "Budi", "role": "mekanik",
            "work_time": {day: {"start": "08:00:00", "end": "17:00:00"} for day in
                          ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")},
            "occupied_time": {day: [{"start": "08:00:00", "end": "15:00:00"}] for day in
                              ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")},
        }])
        wo = _work_order(client)
        assert wo["assigned_technician"] == "Budi"
        assert wo["scheduled_start"][11:16] >= "15:00"
        assert wo["scheduled_end"][11:16] <= "17:00"


def test_no_roster_leaves_the_work_order_unscheduled_but_created():
    with TestClient(app) as client:
        _roster(client, [])
        wo = _work_order(client)
        assert wo["assigned_technician"] is None
        assert wo["schedule_note"] == "no_technicians"


def test_coordinator_reschedules_and_cannot_double_book():
    with TestClient(app) as client:
        _roster(client, [{"name": "Budi", "role": "mekanik", "work_time": ALL_DAY, "occupied_time": {}},
                         {"name": "Sari", "role": "mekanik", "work_time": ALL_DAY, "occupied_time": {}}])
        first = _work_order(client)
        second = _work_order(client)

        moved = client.put(f"/api/v1/work-orders/{second['id']}/assignment", headers=MANAGER, json={
            "technician": "Sari", "start": "2026-09-01T08:00:00Z", "end": "2026-09-01T10:00:00Z",
        })
        assert moved.status_code == 200
        assert moved.json()["assigned_technician"] == "Sari"

        # onto a slot Sari already holds
        clash = client.put(f"/api/v1/work-orders/{first['id']}/assignment", headers=MANAGER, json={
            "technician": "Sari", "start": "2026-09-01T09:00:00Z", "end": "2026-09-01T11:00:00Z",
        })
        assert clash.status_code == 409
        assert clash.json()["error"]["code"] == "CONFLICT"
        assert "double_booked" in clash.json()["error"]["message"]

        # touching the edge is not an overlap
        ok = client.put(f"/api/v1/work-orders/{first['id']}/assignment", headers=MANAGER, json={
            "technician": "Sari", "start": "2026-09-01T10:00:00Z", "end": "2026-09-01T12:00:00Z",
        })
        assert ok.status_code == 200


def test_rescheduling_is_the_coordinators_alone():
    with TestClient(app) as client:
        _roster(client, [{"name": "Budi", "role": "mekanik", "work_time": ALL_DAY, "occupied_time": {}}])
        wo = _work_order(client)
        denied = client.put(f"/api/v1/work-orders/{wo['id']}/assignment", headers={"X-Demo-User": "demo-technician"},
                            json={"technician": "Budi", "start": "2026-09-01T08:00:00Z", "end": "2026-09-01T10:00:00Z"})
        assert denied.status_code == 403


def test_approval_is_the_coordinators_alone():
    with TestClient(app) as client:
        wo = _work_order(client)
        client.post(f"/api/v1/work-orders/{wo['id']}/submit")

        # An engineer proposes; only a coordinator decides.
        assert client.post(f"/api/v1/work-orders/{wo['id']}/approve").status_code == 403
        assert client.post(f"/api/v1/work-orders/{wo['id']}/approve", headers=TECHNICIAN).status_code == 403
        assert client.post(f"/api/v1/work-orders/{wo['id']}/approve", headers=MANAGER).status_code == 200


def test_rejection_records_its_reason():
    with TestClient(app) as client:
        wo = _work_order(client)
        client.post(f"/api/v1/work-orders/{wo['id']}/submit")

        assert client.post(f"/api/v1/work-orders/{wo['id']}/reject", headers=MANAGER, json={}).status_code == 422

        response = client.post(
            f"/api/v1/work-orders/{wo['id']}/reject",
            headers=MANAGER,
            json={"reason": "Sparepart belum datang, tunda ke minggu depan."},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "rejected"
        assert body["details_json"]["rejection_reason"].startswith("Sparepart belum datang")

        # Rejected is terminal.
        assert client.post(f"/api/v1/work-orders/{wo['id']}/approve", headers=MANAGER).status_code == 409


def test_illegal_transitions_are_refused_with_the_pair_named():
    with TestClient(app) as client:
        wo = _work_order(client)
        response = client.post(f"/api/v1/work-orders/{wo['id']}/start")
        assert response.status_code == 409
        assert response.json()["error"]["message"] == "invalid_transition:draft->in_progress"


def test_progress_records_without_completing():
    """Completion goes through verification, not through a percentage field."""
    with TestClient(app) as client:
        wo = _work_order(client)
        for path, headers in (("submit", {}), ("approve", MANAGER), ("schedule", {}), ("start", {})):
            client.post(f"/api/v1/work-orders/{wo['id']}/{path}", headers=headers)

        response = client.post(
            f"/api/v1/work-orders/{wo['id']}/progress",
            headers=TECHNICIAN,
            json={"percentage": 100, "note": "insert diganti"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "in_progress"


def test_result_verification_is_technician_only_idempotent_and_completes(monkeypatch):
    with TestClient(app) as client:
        wo = _work_order(client)
        oid = wo["id"]
        for path, headers in (("submit", {}), ("approve", MANAGER), ("schedule", {}), ("start", {})):
            assert client.post(f"/api/v1/work-orders/{oid}/{path}", headers=headers).status_code == 200
        result = {"work_done": "Bearing replaced", "findings": "Noise resolved", "parts_used": ["SKF-6204"], "evidence": ["photo-1"]}
        assert client.post(f"/api/v1/work-orders/{oid}/result", json=result).status_code == 403
        first = client.post(f"/api/v1/work-orders/{oid}/result", headers=TECHNICIAN, json=result)
        assert first.status_code == 200
        second = client.post(f"/api/v1/work-orders/{oid}/result", headers=TECHNICIAN, json=result)
        assert second.status_code == 200 and second.json()["result"] == first.json()["result"]
        assert client.post(f"/api/v1/work-orders/{oid}/verify").status_code == 200
        assert client.post(f"/api/v1/work-orders/{oid}/verify").json()["status"] == "completed"
        with SessionLocal() as db:
            record = db.query(models.MaintenanceRecord).filter_by(asset_id=wo["asset_id"]).one()
            assert record.source == "work_order_verification"
            actions = {event.action for event in db.query(models.AuditEvent).filter_by(resource_id=oid).all()}
            assert {"work_order.result_submitted", "work_order.verification_completed", "work_order.status_changed"} <= actions

def test_resolved_verification_reports_ingestion_failure_without_failing_verification(monkeypatch):
    class FakeKnowledge:
        def ingest(self, *args, **kwargs): raise RuntimeError("vector unavailable")
    fake_src = types.ModuleType("src")
    fake_src.TechnicianResult = lambda **values: values
    fake_src.WorkOrder = lambda **values: values
    fake_src.VerificationResult = lambda **values: values
    fake_src.Document = lambda **values: values
    fake_src.knowledge = FakeKnowledge()
    with TestClient(app) as client:
        # the fake src also replaces the analysis engine, so build the work order first
        wo = _work_order(client); oid = wo["id"]
        monkeypatch.setitem(sys.modules, "src", fake_src)
        for path, headers in (("submit", {}), ("approve", MANAGER), ("schedule", {}), ("start", {})):
            client.post(f"/api/v1/work-orders/{oid}/{path}", headers=headers)
        client.post(f"/api/v1/work-orders/{oid}/result", headers=TECHNICIAN, json={"work_done": "fixed", "findings": "clear"})
        response = client.post(f"/api/v1/work-orders/{oid}/verify")
        assert response.status_code == 200 and response.json()["status"] == "completed", response.text
        body = response.json()
        assert body["verification"].get("ingestion", {}).get("status") == "failed", response.text
        with SessionLocal() as db:
            document = db.query(models.Document).filter_by(asset_id=wo["asset_id"], kind="maintenance_history").one()
            assert document.ingestion_status == "failed"


def test_resolved_verification_retries_failed_ingestion_without_duplicates(monkeypatch):
    calls = []
    class FakeKnowledge:
        def ingest(self, *args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("temporary vector failure")
            return 1
    fake_src = types.ModuleType("src")
    fake_src.TechnicianResult = lambda **values: values
    fake_src.WorkOrder = lambda **values: values
    fake_src.VerificationResult = lambda **values: values
    fake_src.Document = lambda **values: values
    fake_src.knowledge = FakeKnowledge()
    with TestClient(app) as client:
        # the fake src also replaces the analysis engine, so build the work order first
        wo = _work_order(client); oid = wo["id"]
        monkeypatch.setitem(sys.modules, "src", fake_src)
        for path, headers in (("submit", {}), ("approve", MANAGER), ("schedule", {}), ("start", {})):
            client.post(f"/api/v1/work-orders/{oid}/{path}", headers=headers)
        client.post(f"/api/v1/work-orders/{oid}/result", headers=TECHNICIAN, json={"work_done": "fixed", "findings": "clear"})
        first = client.post(f"/api/v1/work-orders/{oid}/verify")
        second = client.post(f"/api/v1/work-orders/{oid}/verify")
        assert first.json()["verification"]["ingestion"]["status"] == "failed"
        assert second.json()["verification"]["ingestion"]["status"] == "ready"
        with SessionLocal() as db:
            assert db.query(models.MaintenanceRecord).filter_by(asset_id=wo["asset_id"]).count() == 1
            assert db.query(models.Document).filter_by(asset_id=wo["asset_id"], kind="maintenance_history").count() == 1

def _to_in_progress(client, oid):
    for path, headers in (("submit", {}), ("approve", MANAGER), ("schedule", {}), ("start", {})):
        client.post(f"/api/v1/work-orders/{oid}/{path}", headers=headers)


def test_a_rejected_report_can_be_redone_and_resubmitted(monkeypatch):
    verdicts = iter(["not_resolved", "resolved"])
    class Engine:
        mode = "test"
        def analyze(self, request):
            return {"health_score": 50, "priority": "high", "model": "test", "work_order": {"title": "Fix"}}
        def verify(self, work_order, result):
            return {"verdict": next(verdicts), "evidence": [], "follow_up": ["ganti bearing"]}
    monkeypatch.setattr(analysis_service, "engine_factory", lambda settings: Engine())
    with TestClient(app) as client:
        wo = _work_order(client); oid = wo["id"]
        _to_in_progress(client, oid)

        client.post(f"/api/v1/work-orders/{oid}/result", headers=TECHNICIAN,
                    json={"work_done": "dibersihkan", "findings": "kotor"})
        rejected = client.post(f"/api/v1/work-orders/{oid}/verify")
        assert rejected.json()["verification"]["verdict"] == "not_resolved"
        assert rejected.json()["status"] == "in_progress"

        # the technician redoes the work and reports again
        again = client.post(f"/api/v1/work-orders/{oid}/result", headers=TECHNICIAN,
                            json={"work_done": "bearing diganti", "findings": "aus"})
        assert again.status_code == 200, again.text
        assert again.json()["result"]["work_done"] == "bearing diganti"
        assert again.json()["attempts"] == 2

        order = next(o for o in client.get("/api/v1/work-orders").json() if o["id"] == oid)
        # the rejected attempt is kept, not overwritten
        attempts = order["details_json"]["result_attempts"]
        assert len(attempts) == 1
        assert attempts[0]["result"]["work_done"] == "dibersihkan"
        assert attempts[0]["verification"]["verdict"] == "not_resolved"
        # and the stale verdict is gone, so verification runs again
        assert order["verification_json"] is None

        accepted = client.post(f"/api/v1/work-orders/{oid}/verify")
        assert accepted.json()["verification"]["verdict"] == "resolved"
        assert accepted.json()["status"] == "completed"


def test_a_standing_report_still_cannot_be_rewritten(monkeypatch):
    class Engine:
        mode = "test"
        def analyze(self, request):
            return {"health_score": 50, "priority": "high", "model": "test", "work_order": {"title": "Fix"}}
    monkeypatch.setattr(analysis_service, "engine_factory", lambda settings: Engine())
    with TestClient(app) as client:
        wo = _work_order(client); oid = wo["id"]
        _to_in_progress(client, oid)
        client.post(f"/api/v1/work-orders/{oid}/result", headers=TECHNICIAN, json={"work_done": "a", "findings": ""})
        # not verified yet, so nothing was rejected: the report stands
        clash = client.post(f"/api/v1/work-orders/{oid}/result", headers=TECHNICIAN,
                            json={"work_done": "b", "findings": ""})
        assert clash.status_code == 409
        assert clash.json()["error"]["message"] == "conflicting_technician_result"


def test_work_order_export_has_headers_and_tenant_isolation():
    with TestClient(app) as client:
        wo = _work_order(client)
        json_export = client.get(f"/api/v1/work-orders/{wo['id']}/export?format=json")
        csv_export = client.get(f"/api/v1/work-orders/{wo['id']}/export?format=csv")
        assert json_export.status_code == 200 and "attachment" in json_export.headers["content-disposition"]
        assert csv_export.status_code == 200 and "text/csv" in csv_export.headers["content-type"]
        assert client.get(f"/api/v1/work-orders/{wo['id']}/export", headers={"X-Factory-ID": "other"}).status_code == 404
        with SessionLocal() as db:
            events = db.query(models.AuditEvent).filter_by(resource_id=wo["id"], action="work_order.exported").all()
            assert {event.after_json["format"] for event in events} == {"json", "csv"}
            assert all(event.after_json["erp"] == {"external_id": f"ERP-{wo['id'][:8]}", "status": "accepted"} for event in events)


def test_partial_verification_stays_in_progress_and_report_is_scoped(monkeypatch):
    original = analysis_service.engine_factory
    class Partial:
        mode = "test"
        def verify(self, work_order, technician_result):
            return {"verdict": "partial", "evidence": ["photo"], "follow_up": ["Retorque bolts"]}
    try:
        with TestClient(app) as client:
            wo = _work_order(client)
            oid = wo["id"]
            analysis_service.engine_factory = lambda settings: Partial()
            for path, headers in (("submit", {}), ("approve", MANAGER), ("schedule", {}), ("start", {})):
                client.post(f"/api/v1/work-orders/{oid}/{path}", headers=headers)
            client.post(f"/api/v1/work-orders/{oid}/result", headers=TECHNICIAN, json={"work_done": "Partial", "findings": "Still noisy"})
            response = client.post(f"/api/v1/work-orders/{oid}/verify")
            assert response.json()["status"] == "in_progress"
            assert client.get(f"/api/v1/work-orders/{oid}/report").status_code == 200
            assert client.get(f"/api/v1/work-orders/{oid}/report", headers={"X-Factory-ID": "other"}).status_code == 404
    finally:
        analysis_service.engine_factory = original


@pytest.mark.parametrize("verdict, expected_status", [("partial", "in_progress"), ("not_resolved", "in_progress")])
def test_non_resolved_verdicts_never_complete(verdict, expected_status):
    original = analysis_service.engine_factory
    class Fake:
        mode = "test"
        def verify(self, work_order, technician_result):
            return {"verdict": verdict, "evidence": [], "follow_up": ["Inspect again"]}
    try:
        with TestClient(app) as client:
            wo = _work_order(client)
            oid = wo["id"]
            for path, headers in (("submit", {}), ("approve", MANAGER), ("schedule", {}), ("start", {})):
                client.post(f"/api/v1/work-orders/{oid}/{path}", headers=headers)
            analysis_service.engine_factory = lambda settings: Fake()
            client.post(f"/api/v1/work-orders/{oid}/result", headers=TECHNICIAN, json={"work_done": "attempt", "findings": "not fixed"})
            assert client.post(f"/api/v1/work-orders/{oid}/verify").json()["status"] == expected_status
    finally:
        analysis_service.engine_factory = original


def test_conflicting_result_and_failed_verification_are_safe():
    original = analysis_service.engine_factory
    class Broken:
        mode = "test"
        def verify(self, work_order, technician_result):
            raise RuntimeError("unavailable")
    try:
        with TestClient(app) as client:
            wo = _work_order(client)
            oid = wo["id"]
            for path, headers in (("submit", {}), ("approve", MANAGER), ("schedule", {}), ("start", {})):
                client.post(f"/api/v1/work-orders/{oid}/{path}", headers=headers)
            payload = {"work_done": "done", "findings": "unknown"}
            client.post(f"/api/v1/work-orders/{oid}/result", headers=TECHNICIAN, json=payload)
            conflict = client.post(f"/api/v1/work-orders/{oid}/result", headers=TECHNICIAN, json={"work_done": "other"})
            assert conflict.status_code == 409
            analysis_service.engine_factory = lambda settings: Broken()
            failed = client.post(f"/api/v1/work-orders/{oid}/verify")
            assert failed.status_code == 422
            assert client.get(f"/api/v1/work-orders/{oid}/report").status_code == 404
    finally:
        analysis_service.engine_factory = original


def test_factory_scoping_hides_other_tenants():
    with TestClient(app) as client:
        asset = client.post(
            "/api/v1/assets", json={"name": "Punya A"}, headers={"X-Factory-ID": "factory-a"}
        ).json()
        assert client.get(
            f"/api/v1/assets/{asset['id']}", headers={"X-Factory-ID": "factory-b"}
        ).status_code == 404
        assert client.get("/api/v1/assets", headers={"X-Factory-ID": "../etc"}).status_code == 400

def test_new_factory_is_created_before_asset_and_import():
    with TestClient(app) as client:
        headers = {"X-Factory-ID": "new-factory"}
        asset = client.post("/api/v1/assets", headers=headers, json={"name": "Tenant pump"})
        assert asset.status_code == 201
        imported = client.post(
            "/api/v1/assets/import",
            headers={"X-Factory-ID": "another-new-factory"},
            files={"file": ("assets.csv", b"name\nImported pump\n", "text/csv")},
        )
        assert imported.status_code == 200
        assert imported.json()["imported"] == 1
        with SessionLocal() as db:
            assert db.get(models.Factory, "new-factory") is not None
            assert db.get(models.Factory, "another-new-factory") is not None


def test_upload_rejections():
    with TestClient(app) as client:
        assert client.post(
            "/api/v1/knowledge/documents",
            files={"file": ("photo.jpg", b"\xff\xd8\xff", "image/jpeg")},
        ).status_code == 422
        assert client.post(
            "/api/v1/knowledge/documents",
            files={"file": ("big.txt", b"x" * (10 * 1024 * 1024 + 1), "text/plain")},
        ).status_code == 422


def test_patch_asset_round_trips():
    with TestClient(app) as client:
        asset = client.post("/api/v1/assets", json={"name": "Pump"}).json()
        response = client.patch(
            f"/api/v1/assets/{asset['id']}",
            json={"name": "Pump 2", "criticality": "high", "specs_json": {"maintenance_interval_days": 30}},
        )
        assert response.status_code == 200
        assert response.json()["specs"]["maintenance_interval_days"] == 30


def test_error_envelope_shape():
    """One envelope for every error, including FastAPI's own HTTPException."""
    with TestClient(app) as client:
        body = client.get("/api/v1/assets/nope").json()["error"]
        assert body["code"] == "NOT_FOUND"
        assert body["message"] == "asset_not_found"
        assert body["request_id"]

        wo = _work_order(client)
        client.post(f"/api/v1/work-orders/{wo['id']}/submit")
        forbidden = client.post(f"/api/v1/work-orders/{wo['id']}/approve").json()
        assert forbidden["error"]["code"] == "FORBIDDEN"
        assert "engineer" in forbidden["error"]["message"]
        assert forbidden["error"]["request_id"]

        bad_tenant = client.get("/api/v1/assets", headers={"X-Factory-ID": "../etc"}).json()
        assert bad_tenant["error"]["code"] == "VALIDATION_ERROR"


PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")

def test_qc_batch_validates_signatures_scopes_and_audits():
    with TestClient(app) as client:
        asset = client.post("/api/v1/assets", json={"name": "QC pump"}).json()
        aid = asset["id"]
        response = client.post(
            f"/api/v1/assets/{aid}/qc-batches",
            files=[("files", ("front.png", PNG, "text/plain")), ("files", ("side.png", PNG, "image/png"))],
            headers={"X-Request-ID": "qc-request"},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["count"] == 2
        assert body["defect_rate"] == 0
        assert all("storage_key" not in image for image in body["images"])
        assert client.get(f"/api/v1/qc-batches/{body['id']}").json()["count"] == 2
        assert client.get(f"/api/v1/qc-batches/{body['id']}", headers={"X-Factory-ID": "other"}).status_code == 404
        other_asset = client.post("/api/v1/assets", json={"name": "Other QC asset"}).json()
        assert client.post(f"/api/v1/assets/{other_asset['id']}/analyses", json={"qc_batch_id": body["id"]}).status_code == 404
        with SessionLocal() as db:
            event = db.query(models.AuditEvent).filter_by(resource_id=body["id"]).one()
            assert event.action == "qc_batch.created"
            assert event.request_id == "qc-request"

        bad = client.post(
            f"/api/v1/assets/{aid}/qc-batches",
            files={"files": ("fake.png", b"not an image", "image/png")},
        )
        assert bad.status_code == 422
        assert bad.json()["error"]["message"] == "invalid_qc_image_signature"


def test_analysis_rejects_qc_storage_escape(monkeypatch):
    with TestClient(app) as client:
        asset = client.post("/api/v1/assets", json={"name": "QC escape"}).json()
        batch = client.post(f"/api/v1/assets/{asset['id']}/qc-batches", files={"files": ("part.png", PNG, "image/png")}).json()
        with SessionLocal() as db:
            image = db.query(models.QCImage).filter_by(batch_id=batch["id"]).one()
            image.storage_key = "../outside.png"
            db.commit()
        response = client.post(f"/api/v1/assets/{asset['id']}/analyses", json={"qc_batch_id": batch["id"]})
        assert response.status_code == 422
        assert response.json()["error"]["message"] == "invalid_storage_key"

def test_qc_batch_rejects_image_count_and_aggregate_size(monkeypatch):
    with TestClient(app) as client:
        asset = client.post("/api/v1/assets", json={"name": "QC limits"}).json()
        aid = asset["id"]
        monkeypatch.setenv("MAX_QC_IMAGES", "1")
        # Settings is cached, so exercise the limit through a direct temporary setting.
        settings = __import__("app.main", fromlist=["get_settings"]).get_settings()
        old = settings.max_qc_images
        old_batch = settings.max_qc_batch_bytes
        settings.max_qc_images = 1
        try:
            response = client.post(f"/api/v1/assets/{aid}/qc-batches", files=[("files", ("a.png", PNG, "image/png")), ("files", ("b.png", PNG, "image/png"))])
            assert response.status_code == 422
            assert response.json()["error"]["message"] == "too_many_qc_images"
            settings.max_qc_images = 2
            settings.max_qc_batch_bytes = len(PNG)
            response = client.post(f"/api/v1/assets/{aid}/qc-batches", files=[("files", ("a.png", PNG, "image/png")), ("files", ("b.png", PNG, "image/png"))])
            assert response.status_code == 422
            assert response.json()["error"]["message"] == "qc_batch_too_large"
        finally:
            settings.max_qc_images = old
            settings.max_qc_batch_bytes = old_batch

def test_batch_readings_and_mock_ingest_are_idempotent(monkeypatch):
    with TestClient(app) as client:
        asset = client.post("/api/v1/assets", json={"name": "Sensors"}).json()
        aid = asset["id"]
        reading = {"tag": "temp", "value": 61, "recorded_at": "2026-08-23T10:00:00Z", "external_id": "r-1"}
        response = client.post(f"/api/v1/assets/{aid}/readings:batch", json={"readings": [reading, reading]})
        assert response.status_code == 200
        assert response.json()["count"] == 2
        assert response.json()["readings"][0]["id"] == response.json()["readings"][1]["id"]
        pulled = [{**reading, "source": "mock-plc"}]
        monkeypatch.setattr("app.adapters.MockPLC.pull", lambda self, asset_id: pulled)
        ingest = client.post(f"/api/v1/assets/{aid}/ingest/plc")
        assert ingest.status_code == 200
        assert ingest.json()["readings"][0]["id"] == response.json()["readings"][0]["id"]
        assert client.post(f"/api/v1/assets/{aid}/ingest/iot").status_code == 200

def test_analysis_wires_qc_images_and_preserves_snapshot(monkeypatch):
    captured = {}
    class Engine:
        mode = "test"
        def analyze(self, request):
            captured["request"] = request
            return {"health_score": 90, "priority": "low", "model": "test", "work_order": {}}
    monkeypatch.setattr(analysis_service, "engine_factory", lambda settings: Engine())
    with TestClient(app) as client:
        asset = client.post("/api/v1/assets", json={"name": "Vision"}).json()
        batch = client.post(f"/api/v1/assets/{asset['id']}/qc-batches", files={"files": ("part.png", PNG, "image/png")}).json()
        response = client.post(f"/api/v1/assets/{asset['id']}/analyses", json={"qc_batch_id": batch["id"]})
        assert response.status_code == 201
        assert len(captured["request"].images) == 1
        analysis = client.get(f"/api/v1/analyses/{response.json()['id']}").json()
        assert analysis["request_snapshot"]["qc_batch_id"] == batch["id"]
        assert analysis["request_snapshot"]["images"] == captured["request"].images


def test_schedules_survive_the_round_trip_to_the_engine(monkeypatch):
    captured = {}
    class Engine:
        mode = "test"
        def analyze(self, request):
            captured["request"] = request
            return {"health_score": 100, "priority": "low", "model": "test", "work_order": {}}
    monkeypatch.setattr(analysis_service, "engine_factory", lambda settings: Engine())
    schedules = {
        "production_schedule": {"work_time": {"monday": {"start": "06:00:00", "end": "14:00:00"}}},
        "technicians": [
            {
                "name": "Budi", "role": "mechanic", "specialty": "pumps",
                "work_time": {"monday": {"start": "06:00:00", "end": "14:00:00"}},
                "occupied_time": {"monday": [{"start": "08:00:00", "end": "12:00:00"}]},
            },
            {"name": "Sari", "role": "electrician", "work_time": {"friday": {"start": "08:00:00", "end": "16:00:00"}}},
        ],
    }
    with TestClient(app) as client:
        aid = client.post("/api/v1/assets", json={"name": "Pump"}).json()["id"]
        client.put("/api/v1/business-context", json={})

        # nothing configured: engine falls back to its own empty defaults
        first = client.post(f"/api/v1/assets/{aid}/analyses", json={}).json()["id"]
        bare = client.get(f"/api/v1/analyses/{first}").json()
        assert bare["request_snapshot"]["business"]["production_schedule"] is None
        assert "business_context" in bare["input_disclosure"]["missing"]

        assert client.put("/api/v1/business-context", json=schedules).status_code == 200
        assert [t["name"] for t in client.get("/api/v1/business-context").json()["technicians"]] == ["Budi", "Sari"]

        response = client.post(f"/api/v1/assets/{aid}/analyses", json={})
        assert response.status_code == 201
        business = captured["request"].business
        business = business if isinstance(business, dict) else business.model_dump(mode="json")
        assert business["production_schedule"]["work_time"]["monday"]["start"].startswith("06:00")
        assert business["technicians"][0]["occupied_time"]["monday"][0]["end"].startswith("12:00")
        assert business["technicians"][1]["name"] == "Sari"
        analysis = client.get(f"/api/v1/analyses/{response.json()['id']}").json()
        assert analysis["request_snapshot"]["business"]["production_schedule"] == schedules["production_schedule"]
        assert "business_context" in analysis["input_disclosure"]["available"]

        # factory-wide: a second machine inherits the same context, no re-entry
        other = client.post("/api/v1/assets", json={"name": "Lathe"}).json()["id"]
        client.post(f"/api/v1/assets/{other}/analyses", json={})
        assert captured["request"].business.production_schedule.work_time


def test_engine_sees_only_the_parts_that_fit_the_machine(monkeypatch):
    captured = {}
    class Engine:
        mode = "test"
        def analyze(self, request):
            captured["request"] = request
            return {"health_score": 100, "priority": "low", "model": "test", "work_order": {}}
    monkeypatch.setattr(analysis_service, "engine_factory", lambda settings: Engine())
    with TestClient(app) as client:
        pump = client.post("/api/v1/assets", json={"name": "Pump"}).json()["id"]
        lathe = client.post("/api/v1/assets", json={"name": "Lathe"}).json()["id"]
        inventory = [
            {"id": "seal", "name": "pump seal", "stock": 2, "asset_ids": [pump]},
            {"id": "insert", "name": "TNMG insert", "stock": 9, "asset_ids": [lathe]},
            {"id": "belt", "name": "drive belt", "stock": 1, "asset_ids": [pump, lathe]},
            {"id": "orphan", "name": "unassigned bolt", "stock": 5},
        ]
        assert client.put("/api/v1/business-context", json={"inventory": inventory}).status_code == 200
        # the warehouse view keeps every part and its machines
        stored = client.get("/api/v1/business-context").json()["inventory"]
        assert {p["name"] for p in stored} == {"pump seal", "TNMG insert", "drive belt", "unassigned bolt"}
        assert sorted(next(p for p in stored if p["id"] == "belt")["asset_ids"]) == sorted([pump, lathe])

        client.post(f"/api/v1/assets/{pump}/analyses", json={})
        sent = captured["request"].business.inventory
        assert sorted(part.name for part in sent) == ["drive belt", "pump seal"]

        client.post(f"/api/v1/assets/{lathe}/analyses", json={})
        assert sorted(part.name for part in captured["request"].business.inventory) == ["TNMG insert", "drive belt"]


def test_parts_cannot_be_linked_to_another_factorys_machine():
    with TestClient(app) as client:
        mine = client.post("/api/v1/assets", json={"name": "Mine"}).json()["id"]
        response = client.put("/api/v1/business-context", json={
            "inventory": [{"id": "seal", "name": "seal", "asset_ids": [mine, "not-my-asset"]}],
        })
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"


def test_baseline_is_fitted_from_history_and_scores_later_readings(monkeypatch, tmp_path):
    from src import config as engine_config
    monkeypatch.setattr(engine_config, "BASELINE_DIR", str(tmp_path))
    captured = {}
    class Engine:
        mode = "test"
        def analyze(self, request):
            from src.signals import detect_anomalies
            captured["anomalies"] = detect_anomalies(request.readings, request.asset.id)
            return {"health_score": 100, "priority": "low", "model": "test", "work_order": {}}
    monkeypatch.setattr(analysis_service, "engine_factory", lambda settings: Engine())
    with TestClient(app) as client:
        aid = client.post("/api/v1/assets", json={"name": "Pump"}).json()["id"]
        csv = "tag,value,unit,recorded_at\n" + "".join(
            f"bearing_temp_c,{50 + i % 3},c,2026-01-{i + 1:02d}T00:00:00Z\n" for i in range(20)
        )
        imported = client.post(f"/api/v1/assets/{aid}/readings/import",
                               files={"file": ("history.csv", csv, "text/csv")}).json()
        assert imported["count"] == 20

        response = client.post(f"/api/v1/assets/{aid}/baseline")
        assert response.status_code == 201
        assert response.json()["tags"] == {"bearing_temp_c": 20}

        # a uniformly hot batch: nothing stands out within it, but it is not this
        # machine's normal — the batch-local fence alone would report nothing
        for day in range(21, 25):
            client.post(f"/api/v1/assets/{aid}/readings", json={
                "tag": "bearing_temp_c", "value": 80.0, "unit": "c",
                "recorded_at": f"2026-01-{day}T00:00:00Z", "source": "test", "external_id": None,
            })
        client.post(f"/api/v1/assets/{aid}/analyses", json={})
        flagged = captured["anomalies"]
        assert [a.method for a in flagged] == ["robust_z"]
        assert flagged[0].observed == 80.0 and flagged[0].severity == "critical"


def test_baseline_needs_history_and_refuses_to_guess(monkeypatch, tmp_path):
    from src import config as engine_config
    monkeypatch.setattr(engine_config, "BASELINE_DIR", str(tmp_path))
    with TestClient(app) as client:
        aid = client.post("/api/v1/assets", json={"name": "Bare"}).json()["id"]
        # fewer points than MIN_POINTS_PER_TAG: nothing is fitted, and that is reported
        client.post(f"/api/v1/assets/{aid}/readings", json={
            "tag": "torque_nm", "value": 40.0, "unit": "nm",
            "recorded_at": "2026-01-01T00:00:00Z", "source": "test", "external_id": None,
        })
        body = client.post(f"/api/v1/assets/{aid}/baseline").json()
        assert body["tags"] == {} and body["readings_available"] == 1

        from src.signals import detect_anomalies
        from src.schemas import SensorReading
        from datetime import datetime, timezone
        readings = [SensorReading(tag="torque_nm", value=40.0, unit="nm",
                                  recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc))] * 12
        # no baseline on disk -> the fence, not silence and not a crash
        assert detect_anomalies(readings, aid) == []


def test_qc_images_that_reached_no_model_are_reported_unscored(monkeypatch):
    """A missing visual model degrades the analysis, it does not fail it."""
    class Engine:
        mode = "test"
        def analyze(self, request):
            # what the engine returns when vision has no bank: no findings
            return {"health_score": 90, "priority": "low", "model": "test",
                    "defects": [], "qc_by_phase": [], "work_order": {}}
    monkeypatch.setattr(analysis_service, "engine_factory", lambda settings: Engine())
    with TestClient(app) as client:
        aid = client.post("/api/v1/assets", json={"name": "Mill"}).json()["id"]
        batch = client.post(f"/api/v1/assets/{aid}/qc-batches",
                            files=[("files", ("a.png", PNG, "image/png"))]).json()
        response = client.post(f"/api/v1/assets/{aid}/analyses", json={"qc_batch_id": batch["id"]})
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "succeeded"
        disclosure = body["input_disclosure"]
        assert "qc_images" in disclosure["available"]
        assert {"token": "qc_images", "reason": "not_scored"} in disclosure["limitations"]


def test_analysis_include_flags_control_request_and_snapshot(monkeypatch):
    captured = {}
    class Engine:
        mode = "test"
        def analyze(self, request):
            captured["request"] = request
            return {"health_score": 100, "priority": "low", "model": "test", "work_order": {}}
    monkeypatch.setattr(analysis_service, "engine_factory", lambda settings: Engine())
    with TestClient(app) as client:
        asset = client.post("/api/v1/assets", json={"name": "Flags"}).json()
        aid = asset["id"]
        client.put(f"/api/v1/assets/{aid}/condition", json={"condition": "bearing noise"})
        client.put("/api/v1/business-context", json={"inventory": [{"id": "bearing", "name": "bearing", "stock": 0}]})
        client.post(f"/api/v1/assets/{aid}/maintenance-records", json={"performed_at": "2026-01-01T00:00:00Z", "action": "overhaul"})
        response = client.post(f"/api/v1/assets/{aid}/analyses", json={"include_history": False, "include_business_context": False})
        assert response.status_code == 201
        request = captured["request"]
        assert request.history == []
        assert (request.business["operator_report"] if isinstance(request.business, dict) else request.business.operator_report) is None
        snapshot = client.get(f"/api/v1/analyses/{response.json()['id']}").json()["request_snapshot"]
        assert snapshot["history"] == []
        assert snapshot["business"]["inventory"] == []

def test_analysis_failure_is_stored(monkeypatch):
    class Broken:
        mode = "test"
        def analyze(self, request):
            raise RuntimeError("boom")
    monkeypatch.setattr(analysis_service, "engine_factory", lambda settings: Broken())
    with TestClient(app) as client:
        asset = client.post("/api/v1/assets", json={"name": "Failure"}).json()
        response = client.post(f"/api/v1/assets/{asset['id']}/analyses", json={})
        assert response.status_code == 201
        assert response.json()["status"] == "failed"
        assert response.json()["error_code"] == "ANALYSIS_FAILED"
