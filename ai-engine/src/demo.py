from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from random import gauss, randint

from src import (
    AnalysisRequest,
    Asset,
    BusinessContext,
    Document,
    MaintenanceEngine,
    MaintenanceRecord,
    QCBatch,
    SensorReading,
    SparePart,
    Tier,
)
from src import knowledge, vision


def _generate_plates(tmp: Path, count: int = 8) -> Path:
    from PIL import Image, ImageDraw

    normal_dir = tmp / "normal"
    normal_dir.mkdir()
    for i in range(count):
        img = Image.new("L", (224, 224), 200)
        draw = ImageDraw.Draw(img)
        noise = [gauss(0, 10) for _ in range(20)]
        for _ in range(20):
            x, y = randint(0, 223), randint(0, 223)
            r = randint(1, 4)
            gray = max(0, min(255, int(200 + gauss(0, 10))))
            draw.ellipse([x - r, y - r, x + r, y + r], fill=gray)
        img.save(str(normal_dir / f"plate_{i}.png"))
    return normal_dir


def _generate_defective(tmp: Path) -> str:
    from PIL import Image, ImageDraw

    img = Image.new("L", (224, 224), 200)
    draw = ImageDraw.Draw(img)
    for _ in range(20):
        x, y = randint(0, 223), randint(0, 223)
        r = randint(1, 4)
        gray = max(0, min(255, int(200 + gauss(0, 10))))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=gray)
    draw.line([(20, 20), (200, 200)], fill=0, width=3)
    path = str(tmp / "defective.png")
    img.save(path)
    return path


def fixture_request() -> AnalysisRequest:
    now = datetime.now(timezone.utc)
    factory_id = "demo-factory"

    asset = Asset(
        id="pump-01",
        name="Cooling water pump 1",
        type="pump",
        criticality="high",
        install_date=now - timedelta(days=365),
        specs={"max_temp_c": 85, "maintenance_interval_days": 90},
    )

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
        technicians_available=2,
        inventory=[
            SparePart(
                id="skf-6204",
                name="SKF-6204 bearing",
                stock=1,
                min_stock=2,
            ),
            SparePart(
                id="pump-seal",
                name="pump seal",
                stock=0,
                eta="3 days",
            ),
        ],
    )

    sop = Document(
        id="sop-bearing-replacement",
        title="Bearing Replacement SOP",
        kind="sop",
        factory_id=factory_id,
        text=(
            "Replace the bearing when bearing_temp_c reaches 85C. "
            "Use SKF-6204. Shut down the pump before work. "
            "Replacement takes about 2 hours with two technicians."
        ),
    )
    knowledge.ingest(sop, asset_id=asset.id, factory_id=factory_id)

    return AnalysisRequest(
        tier=Tier.PROFESSIONAL,
        asset=asset,
        factory_id=factory_id,
        readings=readings,
        history=history,
        images=[],
        qc_batches=[],
        business=business,
    )


def main() -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("DEEPSEEK_API_KEY is not set; cannot run the demo.")
        return

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        normal_dir = _generate_plates(tmp)
        defective_path = _generate_defective(tmp)

        print("Fitting PatchCore on nominal plates...")
        vision.fit("pump-01", normal_dir)
        print("  done.")

        request = fixture_request()
        request.images = [defective_path]
        request.qc_batches = [
            QCBatch(
                phase="assembly",
                asset_id="pump-01",
                product="pump-01",
                images=[defective_path],
            )
        ]

        engine = MaintenanceEngine()
        result = engine.analyze(request)

    print(json.dumps(result.model_dump(), indent=2, default=str))

    usage = engine.last_usage
    print("\nusage:")
    print("  input_tokens:", usage.input_tokens)
    print("  output_tokens:", usage.output_tokens)
    print("  cache_read_tokens:", usage.cache_read_tokens)


if __name__ == "__main__":
    main()
