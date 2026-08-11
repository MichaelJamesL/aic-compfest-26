"""Runnable end-to-end demo: one fixture machine through the real API.

Run with `python -m src.demo` (requires DEEPSEEK_API_KEY and a Postgres
instance with the knowledge schema).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from src import (
    AnalysisRequest,
    Asset,
    BusinessContext,
    Document,
    MaintenanceEngine,
    MaintenanceRecord,
    SensorReading,
    Tier,
)
from src import knowledge


def fixture_request() -> AnalysisRequest:
    now = datetime.now(timezone.utc)

    asset = Asset(
        id="pump-01",
        name="Cooling water pump 1",
        type="pump",
        criticality="high",
        install_date=now - timedelta(days=365),
        specs={"max_temp_c": 85, "maintenance_interval_days": 90},
    )

    # Bearing temperature drifting up from ~60C to ~90C over 30 hourly readings.
    readings = [
        SensorReading(
            tag="bearing_temp_c",
            value=round(60 + (90 - 60) * i / 29, 1),
            unit="C",
            recorded_at=now - timedelta(hours=29 - i),
        )
        for i in range(30)
    ]

    history = [
        MaintenanceRecord(
            asset_id=asset.id,
            performed_at=now - timedelta(days=120),
            action="Routine maintenance",
            findings="Replaced seals",
        )
    ]

    business = BusinessContext(
        production_schedule="Current production run ends Saturday.",
        spareparts=["SKF-6204 bearing"],
        sparepart_eta="bearing SKF-6204 ETA 5 days",
        technicians_available=2,
    )

    sop = Document(
        id="sop-bearing-replacement",
        title="Bearing Replacement SOP",
        kind="sop",
        text=(
            "Replace the bearing when bearing_temp_c reaches 85C. "
            "Use SKF-6204. Shut down the pump before work. "
            "Replacement takes about 2 hours with two technicians."
        ),
    )
    knowledge.ingest(sop, asset_id=asset.id)

    return AnalysisRequest(
        tier=Tier.PROFESSIONAL,
        asset=asset,
        readings=readings,
        history=history,
        business=business,
    )


def main() -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("DEEPSEEK_API_KEY is not set; cannot run the demo.")
        return

    engine = MaintenanceEngine()
    result = engine.analyze(fixture_request())

    print(json.dumps(result.model_dump(), indent=2, default=str))

    usage = engine.last_usage
    print("\nusage:")
    print("  input_tokens:", usage.input_tokens)
    print("  output_tokens:", usage.output_tokens)
    print("  cache_read_tokens:", usage.cache_read_tokens)


if __name__ == "__main__":
    main()