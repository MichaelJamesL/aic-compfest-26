import os
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["STORAGE_PATH"] = "/tmp/aic-backend-test"
from fastapi.testclient import TestClient
from app.main import app

def test_starter_flow():
    with TestClient(app) as client:
        assert client.get("/health/live").json()["status"] == "ok"
        asset = client.post("/api/v1/assets", json={"name":"Pump 1","asset_type":"pump"}).json()
        aid = asset["id"]
        client.put(f"/api/v1/assets/{aid}/condition", json={"condition":"vibration increased"})
        result = client.post(f"/api/v1/assets/{aid}/analyses", json={"manual_condition":"vibration increased"}).json()
        assert result["status"] == "succeeded"
        wo = client.post(f"/api/v1/analyses/{result['id']}/work-orders").json()
        assert wo["status"] == "draft"
        assert client.get("/api/v1/dashboard/summary").json()["assets"] >= 1

def test_import_and_document():
    with TestClient(app) as client:
        response=client.post("/api/v1/assets/import", files={"file":("assets.csv",b"name,asset_type\nImported,pump\n","text/csv")})
        assert response.json()["imported"] == 1
        doc=client.post("/api/v1/knowledge/documents", files={"file":("sop.txt",b"Lockout procedure","text/plain")}).json()
        assert doc["ingestion_status"] == "pending"


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
            ("complete", {}, "completed"),
        ]
        for path, headers, expected in steps:
            response = client.post(f"/api/v1/work-orders/{order_id}/{path}", headers=headers)
            assert response.status_code == 200, (path, response.text)
            assert response.json()["status"] == expected

        # Terminal: nothing moves a completed order.
        assert client.post(f"/api/v1/work-orders/{order_id}/cancel").status_code == 409


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


def test_factory_scoping_hides_other_tenants():
    with TestClient(app) as client:
        asset = client.post(
            "/api/v1/assets", json={"name": "Punya A"}, headers={"X-Factory-ID": "factory-a"}
        ).json()
        assert client.get(
            f"/api/v1/assets/{asset['id']}", headers={"X-Factory-ID": "factory-b"}
        ).status_code == 404
        assert client.get("/api/v1/assets", headers={"X-Factory-ID": "../etc"}).status_code == 400


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
