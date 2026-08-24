import datetime

from src.schemas import Anomaly, Asset, DefectFinding, MaintenanceRecord, SensorReading, SparePart
from src.signals import detect_anomalies, health_score, shortages


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


def test_low_only_outlier_is_flagged():
    vals = [50.0 + (i % 3) for i in range(20)]
    vals[-1] = 5.0
    out = detect_anomalies(_readings(vals))
    assert len(out) == 1
    assert out[0].observed == 5.0
    assert out[0].severity == "critical"


def test_both_side_outliers_choose_the_most_extreme_fence_distance():
    vals = [50.0 + (i % 3) for i in range(20)]
    vals[-2:] = [5.0, 500.0]
    out = detect_anomalies(_readings(vals))
    assert len(out) == 1
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


def test_naive_sqlite_maintenance_timestamp_is_treated_as_utc():
    asset = Asset(id="a1", name="Pump", type="pump")
    now = datetime.datetime(2026, 8, 10, tzinfo=datetime.timezone.utc)
    old = MaintenanceRecord(
        asset_id="a1",
        performed_at=datetime.datetime(2026, 1, 1),
        action="overhaul",
    )
    score, summary = health_score(asset, [], [old], now=now)
    assert score < 100
    assert "overdue" in summary.lower()


def test_naive_and_aware_history_can_be_compared():
    asset = Asset(id="a1", name="Pump", type="pump")
    now = datetime.datetime(2026, 8, 10, tzinfo=datetime.timezone.utc)
    history = [
        MaintenanceRecord(asset_id="a1", performed_at=datetime.datetime(2026, 1, 1), action="old"),
        MaintenanceRecord(asset_id="a1", performed_at=now - datetime.timedelta(days=1), action="new"),
    ]
    assert health_score(asset, [], history, now=now)[0] == 100


def test_health_score_falls_as_defect_severity_rises():
    asset = Asset(id="a1", name="Pump", type="pump")
    now = datetime.datetime(2026, 8, 10, tzinfo=datetime.timezone.utc)
    low = DefectFinding(image="t.png", score=0.6, threshold=0.5, label="defect", severity="low")
    high = DefectFinding(image="t.png", score=0.95, threshold=0.5, label="defect", severity="high")
    clean_score, _ = health_score(asset, [], [], now=now)
    low_score, _ = health_score(asset, [], [], [low], now=now)
    high_score, _ = health_score(asset, [], [], [high], now=now)
    assert clean_score > low_score > high_score


def test_shortages_match_by_id():
    inv = [SparePart(id="skf-6204", name="SKF-6204 bearing", stock=0)]
    assert "out of stock" in shortages(["SKF-6204"], inv)[0]


def test_shortages_match_by_name():
    inv = [SparePart(id="skf", name="motor bearing", stock=0)]
    blockers = shortages(["replace motor bearing"], inv)
    assert len(blockers) == 1
    assert "motor bearing" in blockers[0]


def test_shortages_no_match_returns_empty():
    inv = [SparePart(id="skf-6204", name="SKF-6204 bearing", stock=0)]
    assert shortages(["some valve"], inv) == []


def test_shortages_nonzero_stock_no_blocker():
    inv = [SparePart(id="skf-6204", name="SKF-6204 bearing", stock=3)]
    assert shortages(["SKF-6204"], inv) == []


def test_shortages_includes_eta():
    inv = [SparePart(id="skf-6204", name="SKF-6204 bearing", stock=0, eta="5 days")]
    blocker = shortages(["SKF-6204"], inv)[0]
    assert "ETA: 5 days" in blocker
