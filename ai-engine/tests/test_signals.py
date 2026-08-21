import datetime

from src.schemas import Anomaly, Asset, DefectFinding, MaintenanceRecord, SensorReading
from src.signals import detect_anomalies, health_score


def _readings(values, tag="bearing_temp_c"):
    base = datetime.datetime(2026, 8, 1, tzinfo=datetime.timezone.utc)
    return [
        SensorReading(tag=tag, value=v, unit="c", recorded_at=base + datetime.timedelta(hours=i))
        for i, v in enumerate(values)
    ]


def test_clean_series_has_no_anomalies():
    vals = [50.0 + (i % 3) for i in range(20)]
    assert detect_anomalies(_readings(vals)) == []


def test_planted_spike_is_flagged():
    vals = [50.0 + (i % 3) for i in range(20)]
    vals[18] = 500.0  # planted spike
    out = detect_anomalies(_readings(vals))
    assert len(out) == 1
    assert out[0].tag == "bearing_temp_c"
    assert out[0].observed == 500.0
    assert out[0].severity == "critical"


def test_too_few_points_returns_empty():
    assert detect_anomalies(_readings([50.0, 60.0, 70.0])) == []


def test_health_score_falls_as_anomalies_worsen():
    asset = Asset(id="a1", name="Pump", type="pump")
    now = datetime.datetime(2026, 8, 10, tzinfo=datetime.timezone.utc)
    low = Anomaly(tag="t", observed=1, expected_range=(0, 2), severity="low", method="iqr")
    high = Anomaly(tag="t", observed=1, expected_range=(0, 2), severity="high", method="iqr")
    clean_score, _ = health_score(asset, [], [], now=now)
    low_score, _ = health_score(asset, [low], [], now=now)
    high_score, _ = health_score(asset, [high], [], now=now)
    assert clean_score > low_score > high_score


def test_overdue_maintenance_deducts():
    asset = Asset(id="a1", name="Pump", type="pump")
    now = datetime.datetime(2026, 8, 10, tzinfo=datetime.timezone.utc)
    old = MaintenanceRecord(
        asset_id="a1",
        performed_at=now - datetime.timedelta(days=200),
        action="overhaul",
    )
    score, summary = health_score(asset, [], [old], now=now)
    assert score < 100
    assert "overdue" in summary.lower()


def test_health_score_falls_as_defect_severity_rises():
    asset = Asset(id="a1", name="Pump", type="pump")
    now = datetime.datetime(2026, 8, 10, tzinfo=datetime.timezone.utc)
    low = DefectFinding(image="t.png", score=0.6, threshold=0.5, label="defect", severity="low")
    high = DefectFinding(image="t.png", score=0.95, threshold=0.5, label="defect", severity="high")
    clean_score, _ = health_score(asset, [], [], now=now)
    low_score, _ = health_score(asset, [], [], [low], now=now)
    high_score, _ = health_score(asset, [], [], [high], now=now)
    assert clean_score > low_score > high_score