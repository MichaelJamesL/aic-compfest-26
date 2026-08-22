from app.services import TRANSITIONS, StubEngine

def test_work_order_state_machine_is_not_reversible():
    assert "completed" not in TRANSITIONS["draft"]
    assert not TRANSITIONS["completed"]

def test_offline_engine_contract_shape():
    request = type("Request", (), {"tier": type("Tier", (), {"value": "starter"})(), "readings": [], "manual_condition": "noise"})()
    result = StubEngine().analyze(request)
    for field in ("health_score", "anomalies", "root_causes", "recommendation", "priority", "work_order"):
        assert field in result
