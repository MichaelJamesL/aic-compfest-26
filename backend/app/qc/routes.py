import uuid, tempfile
from datetime import datetime, timezone
from pathlib import Path
from fastapi import Depends, File, Form, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import QCBatch, QCImage
from ..assets.service import get_asset
from ..auth import Identity, get_identity
from ..config import get_settings
from ..db import get_db
from ..documents.service import factory_storage_key, safe_storage_path
from ..repositories import audit
from .schemas import QCBatchOut, ModelFitOut
from .service import inspect_images, qc_batch_out, valid_image_bytes, QC_EXTENSIONS


def register_routes(app):
    @app.post("/api/v1/assets/{asset_id}/qc-batches", response_model=QCBatchOut, status_code=201)
    async def create_qc_batch(asset_id: str, phase: str = Form(default="inspection"), product: str = Form(default=""), request: Request = None, files: list[UploadFile] = File(...), db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Upload QC images for a production phase and store them as a batch."""
        asset = get_asset(db, asset_id, identity)
        settings = get_settings()
        if not files or len(files) > settings.max_qc_images:
            raise ValueError("too_many_qc_images")
        prepared = []
        total = 0
        for file in files:
            filename = Path(file.filename or "").name
            ext = Path(filename).suffix.lower()
            raw = await file.read(settings.max_qc_image_bytes + 1)
            if not filename or ext not in QC_EXTENSIONS: raise ValueError("unsupported_qc_image")
            if len(raw) > settings.max_qc_image_bytes: raise ValueError("qc_image_too_large")
            actual = QC_EXTENSIONS[ext] if valid_image_bytes(raw, QC_EXTENSIONS[ext]) else None
            if actual is None: raise ValueError("invalid_qc_image_signature")
            total += len(raw)
            if total > settings.max_qc_batch_bytes: raise ValueError("qc_batch_too_large")
            prepared.append((file, filename, actual, raw))
        batch = QCBatch(factory_id=identity.factory_id, asset_id=asset.id, phase=phase, product=product)
        written, rows = [], []
        try:
            db.add(batch); db.flush()
            for _, filename, mime_type, raw in prepared:
                key = f"{factory_storage_key(identity.factory_id)}/qc/{asset.id}/{uuid.uuid4()}{Path(filename).suffix.lower()}"
                path = safe_storage_path(settings, key)
                path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
                written.append(path)
                row = QCImage(factory_id=identity.factory_id, batch_id=batch.id, asset_id=asset.id, filename=filename, mime_type=mime_type, size_bytes=len(raw), storage_key=str(key))
                db.add(row); rows.append(row)
            inspect_images(rows, written, product or asset.asset_type)
            audit(db, identity, request.state.request_id, "qc_batch.created", "qc_batch", batch.id, after={"asset_id": asset.id, "count": len(prepared)})
            db.commit()
        except Exception:
            db.rollback()
            for path in written: path.unlink(missing_ok=True)
            raise
        db.refresh(batch)
        return qc_batch_out(db, batch)

    @app.post("/api/v1/assets/{asset_id}/models", status_code=201, response_model=ModelFitOut)
    async def create_model(asset_id: str, product: str = Form(default=""), request: Request = None, files: list[UploadFile] = File(...), db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Train a PatchCore visual inspection model from reference images."""
        asset = get_asset(db, asset_id, identity)
        product = product or asset.asset_type
        if not files:
            raise ValueError("no_reference_images")
        with tempfile.TemporaryDirectory() as tmp_str:
            normal_dir = Path(tmp_str) / "normal"
            normal_dir.mkdir()
            for file in files:
                filename = Path(file.filename or "").name
                raw = await file.read()
                path = normal_dir / filename
                path.write_bytes(raw)
            try:
                from src import vision
                bank_path = vision.fit(product, normal_dir)
            except ImportError as exc:
                raise ValueError("ai_engine_unavailable") from exc
        audit(db, identity, request.state.request_id, "model.created", "asset", asset.id, after={"product": product, "bank_path": str(bank_path), "images_used": len(files)})
        return {"asset_id": asset.id, "product": product, "bank_path": str(bank_path), "images_used": len(files)}

    @app.get("/api/v1/models")
    def trained_models(identity: Identity = Depends(get_identity)):
        """Which products already have a visual model, so a screen can say what
        re-training would replace.

        Banks are keyed by product and shared across machines of that type, so
        this is deliberately not scoped per asset.
        """
        try:
            from src import config as engine_config
        except ImportError:
            return []
        bank_dir = Path(engine_config.BANK_DIR)
        if not bank_dir.is_dir():
            return []
        return sorted(
            (
                {"product": bank.stem,
                 "size_bytes": bank.stat().st_size,
                 "trained_at": datetime.fromtimestamp(bank.stat().st_mtime, tz=timezone.utc)}
                for bank in bank_dir.glob("*.pt")
            ),
            key=lambda row: row["product"],
        )

    @app.get("/api/v1/qc-batches/{batch_id}", response_model=QCBatchOut)
    def get_qc_batch(batch_id: str, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Return a QC batch with its images and defect summary."""
        batch = db.scalar(select(QCBatch).where(QCBatch.id == batch_id, QCBatch.factory_id == identity.factory_id))
        if not batch: raise ValueError("qc_batch_not_found")
        return qc_batch_out(db, batch)