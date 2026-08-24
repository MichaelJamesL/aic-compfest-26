import os
import pytest
import base64
import sys
import types
import io
import csv as csv_module
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
    monkeypatch.setitem(sys.modules, "src", fake_src)
    with TestClient(app) as client:
        wo = _work_order(client); oid = wo["id"]
        for path, headers in (("submit", {}), ("approve", MANAGER), ("schedule", {}), ("start", {})):
            client.post(f"/api/v1/work-orders/{oid}/{path}", headers=headers)
        client.post(f"/api/v1/work-orders/{oid}/result", headers=TECHNICIAN, json={"work_done": "fixed", "findings": "clear"})
        response = client.post(f"/api/v1/work-orders/{oid}/verify")
        assert response.status_code == 200 and response.json()["status"] == "completed"
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
    monkeypatch.setitem(sys.modules, "src", fake_src)
    with TestClient(app) as client:
        wo = _work_order(client); oid = wo["id"]
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
        client.put(f"/api/v1/assets/{aid}/business-context", json={"operator_report": "bearing noise", "inventory": [{"id": "bearing", "name": "bearing", "stock": 0}]})
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
