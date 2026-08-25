from pathlib import Path
from fastapi import Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..auth import Identity, get_identity
from ..config import get_settings
from ..db import get_db
from ..assets.service import get_asset
from ..documents.service import check_file
from ..maintenance.service import rows_from_upload, clean_row
from .models import Reading
from .schemas import ReadingIn, ReadingBatchIn
from .service import persist_reading


def register_routes(app):
    @app.post("/api/v1/assets/{asset_id}/readings")
    def reading(asset_id: str, data: ReadingIn, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Submit a single sensor reading for an asset."""
        a = get_asset(db, asset_id, identity)
        r = persist_reading(db, a, data); db.commit()
        return {"id": r.id, "quality": r.quality}

    @app.post("/api/v1/assets/{asset_id}/readings:batch")
    def readings_batch(asset_id: str, data: ReadingBatchIn, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Submit a batch of sensor readings in one request."""
        a = get_asset(db, asset_id, identity)
        result = [persist_reading(db, a, item) for item in data.readings]
        db.commit()
        return {"count": len(result), "readings": [{"id": item.id, "quality": item.quality} for item in result]}

    @app.post("/api/v1/assets/{asset_id}/readings/import")
    async def import_readings(asset_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Bulk-import sensor readings from a CSV file."""
        if Path(file.filename or "").suffix.lower() != ".csv":
            raise ValueError("unsupported_import_extension")
        check_file(file, get_settings().max_upload_bytes)
        asset = get_asset(db, asset_id, identity)
        rows = rows_from_upload(file.filename or "", await file.read())
        saved, errors = [], []
        for index, row in enumerate(rows, start=2):
            try:
                saved.append(persist_reading(db, asset, ReadingIn.model_validate(clean_row(row))))
            except Exception as exc:
                errors.append({"row": index, "reason": str(exc)})
        db.commit()
        return {"count": len(saved), "errors": errors, "readings": [{"id": item.id, "quality": item.quality} for item in saved]}

    @app.post("/api/v1/assets/{asset_id}/baseline", status_code=201)
    def fit_baseline(asset_id: str, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Fit the machine's anomaly baseline from the readings already stored for it.

        Import history first; this reads what is in the database, so refitting
        after more history arrives is the same call again.
        """
        asset = get_asset(db, asset_id, identity)
        rows = list(db.scalars(select(Reading).where(Reading.asset_id == asset.id)))
        try:
            from src import baseline
            from src.schemas import SensorReading
        except ImportError as exc:
            raise ValueError("ai_engine_unavailable") from exc
        fitted = baseline.fit(asset.id, [
            SensorReading(tag=r.tag, value=r.value, unit=r.unit, recorded_at=r.recorded_at)
            for r in rows
        ])
        return {"asset_id": asset.id, "tags": fitted, "points_used": sum(fitted.values()),
                "readings_available": len(rows)}

    @app.get("/api/v1/assets/{asset_id}/readings")
    def readings(asset_id: str, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """List all sensor readings for an asset, newest first."""
        get_asset(db, asset_id, identity)
        return list(db.scalars(
            select(Reading).where(Reading.asset_id == asset_id).order_by(Reading.recorded_at.desc())
        ))