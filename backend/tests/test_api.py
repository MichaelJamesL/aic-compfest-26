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
        # Approve: draft -> pending_approval
        assert client.post(f"/api/v1/work-orders/{wo['id']}/approve").status_code == 200
        assert client.get("/api/v1/dashboard/summary").json()["assets"] >= 1

def test_import_and_document():
    with TestClient(app) as client:
        response=client.post("/api/v1/assets/import", files={"file":("assets.csv",b"name,asset_type\nImported,pump\n","text/csv")})
        assert response.json()["imported"] == 1
        doc=client.post("/api/v1/knowledge/documents", files={"file":("sop.txt",b"Lockout procedure","text/plain")}).json()
        assert doc["ingestion_status"] == "pending"
