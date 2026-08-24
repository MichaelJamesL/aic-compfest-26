import csv, io, json
from pathlib import Path
from fastapi import Depends, File, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Asset
from ..auth import Identity, get_identity
from ..config import get_settings
from ..db import get_db
from ..repositories import audit
from ..documents.service import check_file, factory_storage_key
from .schemas import AssetIn, AssetOut, BusinessIn, ConditionIn
from .service import ensure_factory, get_asset


def register_routes(app):
    @app.get("/api/v1/assets", response_model=list[AssetOut])
    def assets(db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """List all assets belonging to the authenticated factory."""
        return list(db.scalars(
            select(Asset).where(Asset.factory_id == identity.factory_id).order_by(Asset.name)
        ))

    @app.post("/api/v1/assets", response_model=AssetOut, status_code=201)
    def create_asset(data: AssetIn, request: Request, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Register a new machine asset for the factory."""
        ensure_factory(db, identity)
        a = Asset(
            factory_id=identity.factory_id, name=data.name, asset_type=data.asset_type,
            criticality=data.criticality, location=data.location,
            specs_json=data.specs_json, external_id=data.external_id,
        )
        db.add(a); db.flush()
        audit(db, identity, request.state.request_id, "asset.created", "asset", a.id, after={"name": a.name})
        db.commit(); db.refresh(a); return a

    @app.get("/api/v1/assets/{asset_id}", response_model=AssetOut)
    def asset_detail(asset_id: str, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Return a single asset by ID."""
        return get_asset(db, asset_id, identity)

    @app.patch("/api/v1/assets/{asset_id}", response_model=AssetOut)
    def update_asset(asset_id: str, data: AssetIn, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Update an asset's details in place."""
        a = get_asset(db, asset_id, identity)
        a.name = data.name; a.asset_type = data.asset_type; a.criticality = data.criticality
        a.location = data.location; a.specs_json = data.specs_json; a.external_id = data.external_id
        db.commit(); db.refresh(a); return a

    @app.post("/api/v1/assets/import")
    async def import_assets(file: UploadFile = File(...), db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Bulk-import assets from a CSV or JSON file."""
        check_file(file, get_settings().max_upload_bytes)
        ensure_factory(db, identity)
        raw = await file.read()
        rows = json.loads(raw) if file.filename.endswith(".json") else list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
        created = []; errors = []; seen_external_ids = set()
        for i, row in enumerate(rows):
            try:
                name = row.get("name", "").strip()
                if not name: errors.append({"row": i, "reason": "missing_name"}); continue
                a = Asset(factory_id=identity.factory_id, name=name, asset_type=row.get("asset_type", "machine"), criticality=row.get("criticality", "medium"), specs_json={}, external_id=row.get("external_id") or None)
                ext_id = row.get("external_id")
                if ext_id:
                    if ext_id in seen_external_ids:
                        errors.append({"row": i, "reason": "duplicate_external_id"}); continue
                    existing = db.scalar(select(Asset).where(Asset.factory_id == identity.factory_id, Asset.external_id == ext_id))
                    if existing:
                        errors.append({"row": i, "reason": "duplicate_external_id", "id": existing.id}); continue
                    seen_external_ids.add(ext_id)
                db.add(a); created.append(a)
            except Exception as e:
                errors.append({"row": i, "reason": str(e)})
        db.commit()
        return {"imported": len(created), "errors": errors}

    @app.put("/api/v1/assets/{asset_id}/condition")
    def condition(asset_id: str, data: ConditionIn, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Set the operator-reported condition for an asset."""
        from .models import BusinessContext
        a = get_asset(db, asset_id, identity)
        c = db.get(BusinessContext, a.id) or BusinessContext(asset_id=a.id, factory_id=identity.factory_id)
        c.operator_report = data.condition; db.add(c); db.commit()
        return {"asset_id": a.id, "condition": data.condition}

    @app.put("/api/v1/assets/{asset_id}/business-context")
    def business(asset_id: str, data: BusinessIn, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Set business context (production schedule, inventory, technician availability, operator report) for an asset."""
        from .models import BusinessContext
        a = get_asset(db, asset_id, identity)
        c = db.get(BusinessContext, a.id) or BusinessContext(asset_id=a.id, factory_id=identity.factory_id)
        c.production_schedule = data.production_schedule
        c.spareparts_json = [sp.model_dump() if hasattr(sp, 'model_dump') else sp for sp in data.inventory]
        c.sparepart_eta = None
        c.technicians_available = data.technicians_available
        c.operator_report = data.operator_report
        db.add(c); db.commit(); return data