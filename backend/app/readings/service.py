from sqlalchemy import select
from ..readings.models import Reading


def persist_reading(db, asset, data):
    if data.external_id is not None:
        existing = db.scalar(select(Reading).where(
            Reading.factory_id == asset.factory_id,
            Reading.asset_id == asset.id,
            Reading.external_id == data.external_id,
        ))
        if existing:
            return existing
    reading = Reading(
        factory_id=asset.factory_id,
        asset_id=asset.id,
        tag=data.tag,
        value=data.value,
        unit=data.unit,
        recorded_at=data.recorded_at,
        source=data.source,
        external_id=data.external_id,
    )
    db.add(reading)
    db.flush()
    return reading