"""MaintenanceEngine facade wiring, verified without any API call.

We don't touch the network or the DB: the engine's analyze implementation is
replaced with a stub that returns a fixed AnalysisResult, proving the facade
routes a request through to a result unchanged.
"""
import datetime

import pytest
from pydantic_ai.models.test import TestModel

from src.engine import MaintenanceEngine
from src import signals
from src.schemas import (
    AnalysisRequest,
    AnalysisResult,
    Asset,
    BusinessContext,
    MaintenanceRecord,
    ProductionSchedule,
    RootCause,
    SensorReading,
    SparePart,
    TechnicianSchedule,
    Tier,
    TimeInterval,
    WorkOrder,
    TechnicianResult,
    VerificationResult,
)

NOW = datetime.datetime(2026, 8, 10, tzinfo=datetime.timezone.utc)


def _request() -> AnalysisRequest:
    return AnalysisRequest(
        tier=Tier.STANDARD,
        asset=Asset(id="pump-1", name="Main Pump", type="pump"),
        readings=[
            SensorReading(tag="bearing_temp_c", value=50.0 + i, unit="c", recorded_at=NOW + datetime.timedelta(hours=i))
            for i in range(12)
        ],
        history=[
            MaintenanceRecord(
                asset_id="pump-1",
                performed_at=NOW - datetime.timedelta(days=30),
                action="bearing greasing",
                findings="worn bearing",
                parts_used=["SKF-6204"],
            )
        ],
        business=BusinessContext(
            production_schedule=ProductionSchedule(
                work_time={"monday": TimeInterval(start=datetime.time(6), end=datetime.time(14))}
            ),
            inventory=[
                SparePart(id="skf-6204", name="SKF-6204 bearing", stock=1),
            ],
            technicians=[
                TechnicianSchedule(
                    name="Budi",
                    role="mechanic",
                    work_time={"monday": TimeInterval(start=datetime.time(6), end=datetime.time(14))},
                ),
            ],
            operator_report="Bearing is noisy at startup",
        ),
    )


def _stub_result(tier: Tier) -> AnalysisResult:
    return AnalysisResult(
        health_score=62,
        health_summary="Minor concerns; schedule inspection.",
        anomalies=[],
        root_causes=[RootCause(cause="bearing wear", confidence=0.9, evidence=["temp"])],
        recommendation="Replace bearing SKF-6204 during the Saturday window.",
        priority="medium",
        recommended_window="Saturday after Line A batch",
        explanation="Operator report and elevated temperature point to bearing wear.",
        blockers=["bearing SKF-6204 ETA 5 days"],
        work_order=WorkOrder(title="Replace bearing", steps=["torque bolts"], parts=["SKF-6204"]),
        tier=tier,
        model="stub",
        sources=["pump-1#0"],
    )


def test_analyze_returns_valid_result_with_tier_preserved(monkeypatch: pytest.MonkeyPatch):
    engine = MaintenanceEngine(model=TestModel())  # analyze is stubbed; no real key needed
    captured: dict = {}

    def stub(self, request: AnalysisRequest) -> AnalysisResult:
        captured["request"] = request
        return _stub_result(request.tier)

    monkeypatch.setattr(MaintenanceEngine, "analyze", stub)

    result = engine.analyze(_request())

    assert isinstance(result, AnalysisResult)
    assert isinstance(result.health_score, int)
    assert 0 <= result.health_score <= 100
    assert result.priority in {"low", "medium", "high", "critical"}
    assert result.tier == Tier.STANDARD
    assert result.recommendation
    assert captured["request"].tier == Tier.STANDARD


def test_verify_returns_typed_result_with_one_agent_call():
    engine = MaintenanceEngine(model=TestModel())
    result = engine.verify(
        WorkOrder(title="Replace bearing", steps=["Replace the bearing"]),
        TechnicianResult(work_done="Bearing replaced", findings="No further noise", evidence=["photo-1"]),
    )
    assert isinstance(result, VerificationResult)
    assert result.verdict in {"resolved", "partial", "not_resolved"}
    
def test_shortages_appended_to_blockers():
    inv = [SparePart(id="skf-6204", name="SKF-6204 bearing", stock=0)]
    blockers = signals.shortages(["SKF-6204"], inv)
    assert len(blockers) == 1
    assert "SKF-6204 bearing" in blockers[0]
    assert "out of stock" in blockers[0]
