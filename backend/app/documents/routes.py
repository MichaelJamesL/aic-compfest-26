import uuid
from pathlib import Path
from fastapi import Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Document
from ..auth import Identity, get_identity
from ..config import get_settings
from ..db import get_db
from ..assets.service import get_asset
from ..repositories import audit
from .schemas import DocumentOut
from .service import (
    check_file, extract_text, factory_storage_key, safe_storage_path,
    DOCUMENT_KINDS, MAX_UPLOAD_SIZE,
)


def register_routes(app):
    @app.post("/api/v1/knowledge/documents", response_model=DocumentOut, status_code=201)
    async def document(file: UploadFile = File(...), kind: str = "sop", asset_id: str | None = None,
                       db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Upload a document (SOP, manual, log, QC standard) and store its extracted text."""
        settings = get_settings()
        check_file(file, settings.max_upload_bytes)
        if asset_id is not None:
            asset = get_asset(db, asset_id, identity)
            asset_id = asset.id
        if kind not in DOCUMENT_KINDS:
            raise ValueError("unsupported_document_kind")
        raw = await file.read()
        safe_key = factory_storage_key(identity.factory_id)
        key = f"{safe_key}/{uuid.uuid4()}-{Path(file.filename or 'upload').name}"
        path = safe_storage_path(settings, key)
        text = extract_text(file.filename or "document", file.content_type, raw)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            d = Document(
                factory_id=identity.factory_id, asset_id=asset_id,
                title=file.filename or "document", kind=kind,
                filename=file.filename or "document",
                mime_type=file.content_type or "application/octet-stream",
                size_bytes=len(raw), storage_key=str(key),
                extracted_text=text, ingestion_status="pending",
            )
            db.add(d); db.commit(); db.refresh(d)
        except Exception:
            db.rollback(); path.unlink(missing_ok=True); raise
        return d

    @app.post("/api/v1/knowledge/documents/{doc_id}/reindex", response_model=DocumentOut)
    async def reindex_document(doc_id: str, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Re-ingest a document's extracted text into the AI knowledge base."""
        d = db.scalar(select(Document).where(Document.id == doc_id, Document.factory_id == identity.factory_id))
        if not d: raise ValueError("document_not_found")
        if not (d.extracted_text or "").strip():
            d.ingestion_status = "failed"; d.ingestion_error = "dokumen tidak punya teks yang bisa diindeks"
            db.commit(); db.refresh(d); return d
        try:
            from src import Document as EngineDocument, knowledge
        except ImportError as exc:
            d.ingestion_status = "failed"; d.ingestion_error = f"ai-engine tidak terpasang: {exc}"
            db.commit(); db.refresh(d); return d
        try:
            knowledge.ingest(
                EngineDocument(id=d.id, title=d.title, kind=d.kind, text=d.extracted_text, factory_id=d.factory_id),
                asset_id=d.asset_id, factory_id=d.factory_id,
            )
        except Exception as exc:
            d.ingestion_status = "failed"; d.ingestion_error = str(exc)[:500]
        else:
            d.ingestion_status = "ready"; d.ingestion_error = None
        db.commit(); db.refresh(d); return d

    @app.get("/api/v1/knowledge/documents", response_model=list[DocumentOut])
    def documents(db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """List all active knowledge documents for the factory."""
        return list(db.scalars(
            select(Document).where(Document.factory_id == identity.factory_id, Document.status == "active")
        ))