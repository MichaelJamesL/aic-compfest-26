import datetime
import sys
import types

from app.services import TRANSITIONS, StubEngine



def _request(values=(), manual_condition=None, history=()):
    base = datetime.datetime(2026, 8, 1, tzinfo=datetime.timezone.utc)
    return type("Request", (), {
        "tier": type("Tier", (), {"value": "starter"})(),
        "asset": type("Asset", (), {"id": "a1", "specs": {}})(),
        "readings": [type("Reading", (), {"tag": "temp", "value": value, "recorded_at": base + datetime.timedelta(hours=index)})() for index, value in enumerate(values)],
        "manual_condition": manual_condition,
        "history": list(history),
    })()

def test_work_order_state_machine_is_not_reversible():
    assert "completed" not in TRANSITIONS["draft"]
    assert not TRANSITIONS["completed"]

def test_offline_engine_contract_shape():
    result = StubEngine().analyze(_request(manual_condition="noise"))
    for field in ("health_score", "anomalies", "root_causes", "recommendation", "priority", "work_order"):
        assert field in result


def test_clean_readings_are_not_penalized_by_count_or_manual_condition():
    clean = [50.0 + (index % 3) for index in range(20)]
    engine = StubEngine()
    assert engine.analyze(_request(clean))["health_score"] == 100
    assert engine.analyze(_request(clean, manual_condition="operator reports vibration"))["health_score"] == 100


def test_stub_uses_anomaly_score_and_history_without_manual_deduction(monkeypatch):
    values = [50.0 + (index % 3) for index in range(20)]
    values[-1] = 500.0
    history = [type("History", (), {"asset_id": "a1", "performed_at": datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc), "action": "overhaul", "findings": ""})()]
    anomaly = type("Anomaly", (), {"model_dump": lambda self, mode: {"tag": "temp", "observed": 500.0, "expected_range": [49.0, 53.0], "severity": "critical", "method": "iqr"}})()
    captured = {}

    def detect(readings):
        captured["readings"] = readings
        return [anomaly]

    def score(asset, anomalies, received_history):
        captured["history"] = received_history
        assert anomalies == [anomaly]
        return 42, "Significant degradation."

    fake_package = types.ModuleType("src")
    fake_signals = types.ModuleType("src.signals")
    fake_signals.detect_anomalies = detect
    fake_signals.health_score = score
    fake_package.__path__ = []
    monkeypatch.setitem(sys.modules, "src", fake_package)
    monkeypatch.setitem(sys.modules, "src.signals", fake_signals)

    result = StubEngine().analyze(_request(values, history=history))
    assert result["anomalies"][0]["observed"] == 500.0
    assert result["health_score"] == 42
    assert captured["readings"]
    assert captured["history"] == history


def test_stub_fallback_detects_outlier_without_ai_package(monkeypatch):
    monkeypatch.setitem(sys.modules, "src", None)
    monkeypatch.setitem(sys.modules, "src.signals", None)
    values = [50.0 + (index % 3) for index in range(20)]
    values[-1] = 500.0
    result = StubEngine().analyze(_request(values))
    assert result["anomalies"][0]["observed"] == 500.0
    assert result["health_score"] < 100
