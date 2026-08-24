from pathlib import Path
from fastapi import Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import MaintenanceRecord
from ..assets.models import Asset
from ..assets.service import ensure_factory, get_asset
from ..auth import Identity, get_identity
from ..config import get_settings
from ..db import get_db
from ..documents.service import check_file, ALLOWED_EXTENSIONS
from .schemas import MaintenanceIn
from .service import rows_from_upload, clean_row


def register_routes(app):
    @app.post("/api/v1/maintenance-records/import")
    async def import_maintenance_records(file: UploadFile = File(...), db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Bulk-import maintenance records from a CSV or XLSX file."""
        if Path(file.filename or "").suffix.lower() not in {".csv", ".xlsx"}:
            raise ValueError("unsupported_import_extension")
        check_file(file, get_settings().max_upload_bytes, ALLOWED_EXTENSIONS | {".xlsx"})
        ensure_factory(db, identity)
        try:
            rows = rows_from_upload(file.filename or "", await file.read())
        except UnicodeDecodeError as exc:
            raise ValueError("invalid_csv") from exc
        imported, errors = 0, []
        for index, raw_row in enumerate(rows, start=2):
            row = clean_row(raw_row)
            try:
                asset = None
                if row.get("asset_id"):
                    asset = get_asset(db, str(row["asset_id"]), identity)
                elif row.get("asset_external_id"):
                    asset = db.scalar(select(Asset).where(Asset.factory_id == identity.factory_id, Asset.external_id == str(row["asset_external_id"])))
                    if not asset:
                        raise ValueError("asset_not_found")
                else:
                    raise ValueError("missing_asset")
                performed_at = row.get("performed_at")
                action = str(row.get("action") or "").strip()
                if not performed_at: raise ValueError("missing_performed_at")
                if not action: raise ValueError("missing_action")
                external_id = str(row.get("external_id") or "").strip() or None
                if external_id:
                    existing = db.scalar(select(MaintenanceRecord).where(MaintenanceRecord.factory_id == identity.factory_id, MaintenanceRecord.external_id == external_id))
                    if existing:
                        errors.append({"row": index, "reason": "duplicate_external_id", "id": existing.id})
                        continue
                parts = row.get("parts_used", "")
                if isinstance(parts, str):
                    parts = [part.strip() for part in parts.split(",") if part.strip()]
                record = MaintenanceRecord(
                    factory_id=identity.factory_id, asset_id=asset.id,
                    performed_at=MaintenanceIn.model_validate({"performed_at": performed_at, "action": action}).performed_at,
                    action=action, findings=str(row.get("findings") or ""),
                    parts_used_json=parts or [], source="import", external_id=external_id,
                )
                db.add(record); imported += 1
            except Exception as exc:
                errors.append({"row": index, "reason": str(exc)})
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            raise ValueError("maintenance_import_failed") from exc
        return {"imported": imported, "errors": errors}

    @app.post("/api/v1/assets/{asset_id}/maintenance-records", status_code=201)
    def maintenance(asset_id: str, data: MaintenanceIn, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Record a single maintenance action for an asset."""
        a = get_asset(db, asset_id, identity)
        if data.external_id:
            existing = db.scalar(select(MaintenanceRecord).where(MaintenanceRecord.factory_id == identity.factory_id, MaintenanceRecord.external_id == data.external_id))
            if existing: return {"id": existing.id}
        r = MaintenanceRecord(
            factory_id=identity.factory_id, asset_id=a.id, performed_at=data.performed_at,
            action=data.action, findings=data.findings, parts_used_json=data.parts_used,
            external_id=data.external_id,
        )
        db.add(r)
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            raise ValueError("maintenance_record_failed") from exc
        return {"id": r.id}