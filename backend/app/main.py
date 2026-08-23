from contextlib import asynccontextmanager
import re
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import csv, io, json, uuid
from PIL import Image
from fastapi import Depends, FastAPI, File, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from . import models
from .auth import Identity, get_identity, require_role
from .config import get_settings
from .db import get_db, init_db
from .errors import error_response
from .repositories import audit, one_or_404
from .schemas import *
from .services import input_disclosure, persist_reading, run_analysis, submit_technician_result, transition, verify_work_order
from .adapters import MockPLC, MockIoT, MockERP

@asynccontextmanager
async def lifespan(app):
    init_db(); get_settings().storage_path.mkdir(parents=True, exist_ok=True)
    with next(get_db()) as db:
        if not db.get(models.Factory, "demo-factory"):
            db.add(models.Factory(id="demo-factory", name="Demo Factory", deployment_tier=get_settings().deployment_tier)); db.commit()
    yield
app = FastAPI(title="AIC Predictive Maintenance Backend", version="0.1.0", lifespan=lifespan)

@app.middleware("http")
async def request_id(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:36]
    response = await call_next(request); response.headers["X-Request-ID"] = request.state.request_id; return response

def _factory_storage_key(factory_id: str) -> str:
    """Safe storage-key prefix. Rejects anything that could escape the root."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", factory_id):
        raise ValueError("invalid_factory_id")
    return factory_id

def _safe_storage_path(settings, key: str) -> Path:
    root = settings.storage_path.resolve()
    path = (root / key).resolve()
    if root not in path.parents:
        raise ValueError("invalid_storage_key")
    return path

def ensure_factory(db: Session, identity: Identity) -> models.Factory:
    factory = db.get(models.Factory, identity.factory_id)
    if factory is None:
        factory = models.Factory(
            id=identity.factory_id,
            name=identity.factory_id,
            deployment_tier=get_settings().deployment_tier,
        )
        db.add(factory)
        db.flush()
    return factory

def get_asset(db, asset_id, identity):
    try: return one_or_404(db, models.Asset, asset_id, identity.factory_id)
    except ValueError: raise ValueError("asset_not_found")

@app.get("/health/live")
def live(): return {"status": "ok"}
@app.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    database = "ok"
    storage = "ok"
    try:
        db.execute(select(func.count()).select_from(models.Factory))
    except Exception:
        database = "error"
    try:
        storage_path = get_settings().storage_path
        storage_path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=storage_path, prefix=".ready-", delete=True) as probe:
            probe.write(b"ready")
            probe.flush()
    except Exception:
        storage = "error"
    if database != "ok" or storage != "ok":
        return JSONResponse(status_code=503, content={"status": "not_ready", "database": database, "storage": storage})
    return {"status": "ready", "database": database, "storage": storage}
@app.get("/config/capabilities")
def capabilities():
    s=get_settings(); return {"tier": s.deployment_tier, "capabilities": {"assets": True, "documents": True, "analysis": True, "work_orders": True, "mock_plc": True, "ai_engine": s.ai_engine_enabled}}

@app.get("/api/v1/assets", response_model=list[AssetOut])
def assets(db: Session=Depends(get_db), identity: Identity=Depends(get_identity)): return list(db.scalars(select(models.Asset).where(models.Asset.factory_id==identity.factory_id).order_by(models.Asset.name)))
@app.post("/api/v1/assets", response_model=AssetOut, status_code=201)
def create_asset(data: AssetIn, request: Request, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    ensure_factory(db, identity)
    a=models.Asset(factory_id=identity.factory_id, name=data.name, asset_type=data.asset_type, criticality=data.criticality, location=data.location, specs_json=data.specs_json, external_id=data.external_id); db.add(a); db.flush(); audit(db,identity,request.state.request_id,"asset.created","asset",a.id,after={"name":a.name}); db.commit(); db.refresh(a); return a
@app.get("/api/v1/assets/{asset_id}", response_model=AssetOut)
def asset_detail(asset_id: str, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)): return get_asset(db,asset_id,identity)
@app.patch("/api/v1/assets/{asset_id}", response_model=AssetOut)
def update_asset(asset_id: str, data: AssetIn, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    a=get_asset(db,asset_id,identity); a.name=data.name; a.asset_type=data.asset_type; a.criticality=data.criticality; a.location=data.location; a.specs_json=data.specs_json; a.external_id=data.external_id; db.commit(); db.refresh(a); return a
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
MAX_PDF_PAGES = 200
MAX_PDF_TEXT = 2_000_000
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".pdf"}
DOCUMENT_KINDS = {"sop", "manual", "log", "qc_standard", "maintenance_history"}

def _extract_text(filename: str, content_type: str | None, raw: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw), strict=False)
            if len(reader.pages) > MAX_PDF_PAGES:
                raise ValueError("pdf_too_many_pages")
            parts, total = [], 0
            for page in reader.pages:
                part = page.extract_text() or ""
                total += len(part)
                if total > MAX_PDF_TEXT:
                    raise ValueError("pdf_text_too_large")
                parts.append(part)
            return "\n".join(parts).strip()
        except Exception as exc:
            if str(exc) in {"pdf_too_many_pages", "pdf_text_too_large"}:
                raise
            raise ValueError("invalid_pdf") from exc
    if (content_type or "").startswith("text/") or ext in {".txt", ".md", ".csv", ".json"}:
        return raw.decode("utf-8", errors="replace")
    return ""

def _check_file(file: UploadFile, max_size: int = MAX_UPLOAD_SIZE, allowed_extensions=None) -> None:
    if not file.filename: raise ValueError("empty_filename")
    ext = Path(file.filename).suffix.lower()
    if ext not in (allowed_extensions or ALLOWED_EXTENSIONS): raise ValueError(f"unsupported_extension:{ext}")
    preview = file.file.read(max_size + 1)
    file.file.seek(0)
    if len(preview) > max_size: raise ValueError("file_too_large")
    binary_allowed = allowed_extensions or {".csv", ".json", ".pdf"}
    if not (file.content_type or "").startswith("text/") and not ext in binary_allowed:
        # Try to decode as text; if fail, reject for non-text uploads in Starter
        try: preview.decode("utf-8")
        except UnicodeDecodeError: raise ValueError("non_text_file")

@app.post("/api/v1/assets/import")
async def import_assets(file: UploadFile=File(...), db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    _check_file(file, get_settings().max_upload_bytes)
    ensure_factory(db, identity)
    raw=await file.read(); 
    rows=json.loads(raw) if file.filename.endswith(".json") else list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    created=[]; errors=[]; seen_external_ids=set()
    for i, row in enumerate(rows):
        try:
            name = row.get("name", "").strip()
            if not name: errors.append({"row": i, "reason": "missing_name"}); continue
            a=models.Asset(factory_id=identity.factory_id,name=name,asset_type=row.get("asset_type","machine"),criticality=row.get("criticality","medium"),specs_json={}, external_id=row.get("external_id") or None)
            # Idempotent by external_id if provided
            ext_id = row.get("external_id")
            if ext_id:
                if ext_id in seen_external_ids:
                    errors.append({"row": i, "reason": "duplicate_external_id"}); continue
                existing = db.scalar(select(models.Asset).where(models.Asset.factory_id==identity.factory_id, models.Asset.external_id==ext_id))
                if existing: 
                    errors.append({"row": i, "reason": "duplicate_external_id", "id": existing.id}); continue
                seen_external_ids.add(ext_id)
            db.add(a); created.append(a)
        except Exception as e:
            errors.append({"row": i, "reason": str(e)})
    db.commit(); return {"imported":len(created), "errors": errors}

@app.post("/api/v1/knowledge/documents", response_model=DocumentOut, status_code=201)
async def document(file: UploadFile=File(...), kind: str="sop", asset_id: str|None=None, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    settings = get_settings()
    _check_file(file, settings.max_upload_bytes)
    if asset_id is not None:
        asset = get_asset(db, asset_id, identity)
        asset_id = asset.id
    if kind not in DOCUMENT_KINDS: raise ValueError("unsupported_document_kind")
    raw=await file.read(); 
    safe_key=_factory_storage_key(identity.factory_id); key=f"{safe_key}/{uuid.uuid4()}-{Path(file.filename or 'upload').name}"; path=_safe_storage_path(settings, key)
    text = _extract_text(file.filename or "document", file.content_type, raw)
    try:
        path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(raw)
        d=models.Document(factory_id=identity.factory_id,asset_id=asset_id,title=file.filename or "document",kind=kind,filename=file.filename or "document",mime_type=file.content_type or "application/octet-stream",size_bytes=len(raw),storage_key=str(key),extracted_text=text,ingestion_status="pending"); db.add(d); db.commit(); db.refresh(d)
    except Exception:
        db.rollback(); path.unlink(missing_ok=True); raise
    return d

def _rows_from_upload(filename: str, raw: bytes) -> list[dict]:
    ext = Path(filename).suffix.lower()
    if ext == ".csv":
        return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    if ext == ".xlsx":
        try:
            from openpyxl import load_workbook
            sheet = load_workbook(io.BytesIO(raw), read_only=True, data_only=True).active
            values = list(sheet.values)
        except Exception as exc:
            raise ValueError("invalid_xlsx") from exc
        if not values: return []
        headers = [str(value).strip() if value is not None else "" for value in values[0]]
        return [dict(zip(headers, row)) for row in values[1:]]
    raise ValueError("unsupported_import_extension")

def _clean_row(row: dict) -> dict:
    return {str(key).strip(): (value.strip() if isinstance(value, str) else value) for key, value in row.items() if key is not None}

@app.post("/api/v1/maintenance-records/import")
async def import_maintenance_records(file: UploadFile = File(...), db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
    if Path(file.filename or "").suffix.lower() not in {".csv", ".xlsx"}: raise ValueError("unsupported_import_extension")
    _check_file(file, get_settings().max_upload_bytes, ALLOWED_EXTENSIONS | {".xlsx"})
    ensure_factory(db, identity)
    try:
        rows = _rows_from_upload(file.filename or "", await file.read())
    except UnicodeDecodeError as exc:
        raise ValueError("invalid_csv") from exc
    imported, errors = 0, []
    for index, raw_row in enumerate(rows, start=2):
        row = _clean_row(raw_row)
        try:
            asset = None
            if row.get("asset_id"):
                asset = get_asset(db, str(row["asset_id"]), identity)
            elif row.get("asset_external_id"):
                asset = db.scalar(select(models.Asset).where(models.Asset.factory_id == identity.factory_id, models.Asset.external_id == str(row["asset_external_id"])))
                if not asset: raise ValueError("asset_not_found")
            else: raise ValueError("missing_asset")
            performed_at = row.get("performed_at")
            action = str(row.get("action") or "").strip()
            if not performed_at: raise ValueError("missing_performed_at")
            if not action: raise ValueError("missing_action")
            external_id = str(row.get("external_id") or "").strip() or None
            if external_id:
                existing = db.scalar(select(models.MaintenanceRecord).where(models.MaintenanceRecord.factory_id == identity.factory_id, models.MaintenanceRecord.external_id == external_id))
                if existing:
                    errors.append({"row": index, "reason": "duplicate_external_id", "id": existing.id})
                    continue
            parts = row.get("parts_used", "")
            if isinstance(parts, str): parts = [part.strip() for part in parts.split(",") if part.strip()]
            record = models.MaintenanceRecord(factory_id=identity.factory_id, asset_id=asset.id, performed_at=MaintenanceIn.model_validate({"performed_at": performed_at, "action": action}).performed_at, action=action, findings=str(row.get("findings") or ""), parts_used_json=parts or [], source="import", external_id=external_id)
            db.add(record); imported += 1
        except Exception as exc:
            errors.append({"row": index, "reason": str(exc)})
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise ValueError("maintenance_import_failed") from exc
    return {"imported": imported, "errors": errors}
@app.post("/api/v1/assets/{asset_id}/readings")
def reading(asset_id: str, data: ReadingIn, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    a=get_asset(db,asset_id,identity)
    r=persist_reading(db, a, data); db.commit(); return {"id":r.id,"quality":r.quality}
@app.post("/api/v1/assets/{asset_id}/readings:batch")
def readings_batch(asset_id: str, data: ReadingBatchIn, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    a=get_asset(db,asset_id,identity)
    result=[persist_reading(db, a, item) for item in data.readings]
    db.commit()
    return {"count":len(result),"readings":[{"id":item.id,"quality":item.quality} for item in result]}

@app.post("/api/v1/assets/{asset_id}/readings/import")
async def import_readings(asset_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
    if Path(file.filename or "").suffix.lower() != ".csv": raise ValueError("unsupported_import_extension")
    _check_file(file, get_settings().max_upload_bytes)
    asset = get_asset(db, asset_id, identity)
    rows = _rows_from_upload(file.filename or "", await file.read())
    saved, errors = [], []
    for index, row in enumerate(rows, start=2):
        try:
            saved.append(persist_reading(db, asset, ReadingIn.model_validate(_clean_row(row))))
        except Exception as exc:
            errors.append({"row": index, "reason": str(exc)})
    db.commit()
    return {"count": len(saved), "errors": errors, "readings": [{"id": item.id, "quality": item.quality} for item in saved]}
@app.get("/api/v1/assets/{asset_id}/readings")
def readings(asset_id: str, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)): get_asset(db,asset_id,identity); return list(db.scalars(select(models.Reading).where(models.Reading.asset_id==asset_id).order_by(models.Reading.recorded_at.desc())))

@app.put("/api/v1/assets/{asset_id}/condition")
def condition(asset_id: str, data: ConditionIn, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    a=get_asset(db,asset_id,identity); c=db.get(models.BusinessContext,a.id) or models.BusinessContext(asset_id=a.id,factory_id=identity.factory_id); c.operator_report=data.condition; db.add(c); db.commit(); return {"asset_id":a.id,"condition":data.condition}
@app.put("/api/v1/assets/{asset_id}/business-context")
def business(asset_id: str, data: BusinessIn, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    a=get_asset(db,asset_id,identity); c=db.get(models.BusinessContext,a.id) or models.BusinessContext(asset_id=a.id,factory_id=identity.factory_id); c.production_schedule=data.production_schedule; c.spareparts_json=data.spareparts; c.sparepart_eta=data.sparepart_eta; c.technicians_available=data.technicians_available; c.operator_report=data.operator_report; db.add(c); db.commit(); return data
@app.post("/api/v1/assets/{asset_id}/maintenance-records", status_code=201)
def maintenance(asset_id: str, data: MaintenanceIn, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    a=get_asset(db,asset_id,identity)
    if data.external_id:
        existing = db.scalar(select(models.MaintenanceRecord).where(models.MaintenanceRecord.factory_id == identity.factory_id, models.MaintenanceRecord.external_id == data.external_id))
        if existing: return {"id": existing.id}
    r=models.MaintenanceRecord(factory_id=identity.factory_id,asset_id=a.id,performed_at=data.performed_at,action=data.action,findings=data.findings,parts_used_json=data.parts_used,external_id=data.external_id); db.add(r)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise ValueError("maintenance_record_failed") from exc
    return {"id":r.id}

QC_EXTENSIONS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

def _valid_image_bytes(raw: bytes, mime_type: str) -> bool:
    signature = PNG_SIGNATURE if mime_type == "image/png" else b"\xff\xd8\xff"
    if not raw.startswith(signature):
        return False
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        return True
    except (OSError, ValueError):
        return False

@app.post("/api/v1/assets/{asset_id}/qc-batches", response_model=QCBatchOut, status_code=201)
async def create_qc_batch(asset_id: str, request: Request, files: list[UploadFile] = File(...), db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
    asset = get_asset(db, asset_id, identity)
    settings = get_settings()
    if not files or len(files) > settings.max_qc_images: raise ValueError("too_many_qc_images")
    prepared = []
    total = 0
    for file in files:
        filename = Path(file.filename or "").name
        ext = Path(filename).suffix.lower()
        raw = await file.read(settings.max_qc_image_bytes + 1)
        if not filename or ext not in QC_EXTENSIONS: raise ValueError("unsupported_qc_image")
        if len(raw) > settings.max_qc_image_bytes: raise ValueError("qc_image_too_large")
        actual = QC_EXTENSIONS[ext] if _valid_image_bytes(raw, QC_EXTENSIONS[ext]) else None
        if actual is None: raise ValueError("invalid_qc_image_signature")
        total += len(raw)
        if total > settings.max_qc_batch_bytes: raise ValueError("qc_batch_too_large")
        prepared.append((file, filename, actual, raw))
    batch = models.QCBatch(factory_id=identity.factory_id, asset_id=asset.id)
    written = []
    try:
        db.add(batch); db.flush()
        for _, filename, mime_type, raw in prepared:
            key = f"{_factory_storage_key(identity.factory_id)}/qc/{asset.id}/{uuid.uuid4()}{Path(filename).suffix.lower()}"
            path = _safe_storage_path(settings, key)
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
            written.append(path)
            db.add(models.QCImage(factory_id=identity.factory_id, batch_id=batch.id, asset_id=asset.id, filename=filename, mime_type=mime_type, size_bytes=len(raw), storage_key=str(key)))
        audit(db, identity, request.state.request_id, "qc_batch.created", "qc_batch", batch.id, after={"asset_id": asset.id, "count": len(prepared)})
        db.commit()
    except Exception:
        db.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise
    db.refresh(batch)
    return qc_batch_out(db, batch)

def qc_batch_out(db, batch):
    images = list(db.scalars(select(models.QCImage).where(models.QCImage.batch_id == batch.id).order_by(models.QCImage.created_at)))
    defect_count = sum(image.defect_class is not None for image in images)
    return {"id": batch.id, "asset_id": batch.asset_id, "factory_id": batch.factory_id, "count": len(images), "defect_count": defect_count, "defect_rate": defect_count / len(images) if images else 0, "images": images, "created_at": batch.created_at}

@app.get("/api/v1/qc-batches/{batch_id}", response_model=QCBatchOut)
def get_qc_batch(batch_id: str, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
    batch = db.scalar(select(models.QCBatch).where(models.QCBatch.id == batch_id, models.QCBatch.factory_id == identity.factory_id))
    if not batch: raise ValueError("qc_batch_not_found")
    return qc_batch_out(db, batch)

def ingest_mock(asset_id, adapter, db, identity):
    asset = get_asset(db, asset_id, identity)
    pulled = adapter.pull(asset.id)
    saved = []
    for item in pulled:
        item = dict(item)
        item.pop("asset_id", None)
        saved.append(persist_reading(db, asset, ReadingIn(**item)))
    db.commit()
    return {"count": len(saved), "readings": [{"id": item.id, "quality": item.quality} for item in saved]}

@app.post("/api/v1/assets/{asset_id}/ingest/plc")
def ingest_plc(asset_id: str, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
    return ingest_mock(asset_id, MockPLC(), db, identity)

@app.post("/api/v1/assets/{asset_id}/ingest/iot")
def ingest_iot(asset_id: str, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
    return ingest_mock(asset_id, MockIoT(), db, identity)


@app.post("/api/v1/knowledge/documents/{doc_id}/reindex", response_model=DocumentOut)
async def reindex_document(doc_id: str, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    d=db.scalar(select(models.Document).where(models.Document.id==doc_id,models.Document.factory_id==identity.factory_id))
    if not d: raise ValueError("document_not_found")
    # Attempt ingestion via ai-engine if available
    if not (d.extracted_text or "").strip():
        d.ingestion_status="failed"; d.ingestion_error="dokumen tidak punya teks yang bisa diindeks"
        db.commit(); db.refresh(d); return d
    try:
        from src import Document as EngineDocument, knowledge
    except ImportError as exc:
        d.ingestion_status="failed"; d.ingestion_error=f"ai-engine tidak terpasang: {exc}"
        db.commit(); db.refresh(d); return d
    try:
        knowledge.ingest(EngineDocument(id=d.id, title=d.title, kind=d.kind, text=d.extracted_text, factory_id=d.factory_id), asset_id=d.asset_id, factory_id=d.factory_id)
    except Exception as exc:
        d.ingestion_status="failed"; d.ingestion_error=str(exc)[:500]
    else:
        d.ingestion_status="ready"; d.ingestion_error=None
    db.commit(); db.refresh(d); return d

@app.get("/api/v1/knowledge/documents", response_model=list[DocumentOut])
def documents(db: Session=Depends(get_db), identity: Identity=Depends(get_identity)): return list(db.scalars(select(models.Document).where(models.Document.factory_id==identity.factory_id,models.Document.status=="active")))

def analysis_response(run, include_snapshot=False):
    response = {"id": run.id, "status": run.status, "result": run.result_json,
                "input_disclosure": input_disclosure(run.request_snapshot_json),
                "engine_mode": run.engine_mode, "error": run.error_message,
                "error_code": run.error_code, "error_message": run.error_message,
                "health_score": run.health_score, "priority": run.priority}
    if include_snapshot:
        response["request_snapshot"] = run.request_snapshot_json
    return response

@app.post("/api/v1/assets/{asset_id}/analyses", status_code=201)
def analyze(asset_id: str, data: AnalysisIn, request: Request, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    a=get_asset(db,asset_id,identity); run=run_analysis(db,a,data,identity,request.state.request_id,get_settings()); return analysis_response(run)
@app.get("/api/v1/analyses/{analysis_id}")
def analysis(analysis_id: str, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    r=db.scalar(select(models.AnalysisRun).where(models.AnalysisRun.id==analysis_id,models.AnalysisRun.factory_id==identity.factory_id));
    if not r: raise ValueError("analysis_not_found")
    return analysis_response(r, include_snapshot=True)
@app.get("/api/v1/assets/{asset_id}/analyses")
def analysis_history(asset_id: str, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)): get_asset(db,asset_id,identity); return list(db.scalars(select(models.AnalysisRun).where(models.AnalysisRun.asset_id==asset_id).order_by(models.AnalysisRun.created_at.desc())))
@app.post("/api/v1/assets/{asset_id}/ask")
def ask(asset_id: str, data: AskIn, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    a=get_asset(db,asset_id,identity)
    readings = list(db.scalars(select(models.Reading).where(models.Reading.asset_id==a.id).order_by(models.Reading.recorded_at.desc()).limit(50)))
    history = list(db.scalars(select(models.MaintenanceRecord).where(models.MaintenanceRecord.asset_id==a.id).order_by(models.MaintenanceRecord.performed_at.desc()).limit(10)))
    context = db.get(models.BusinessContext, a.id)
    business = {"production_schedule": context.production_schedule if context else None, "spareparts": context.spareparts_json if context else [], "sparepart_eta": context.sparepart_eta if context else None, "technicians_available": context.technicians_available if context else None, "operator_report": context.operator_report if context else None}
    from .services import engine_factory, engine_request
    req = engine_request(a, readings, history, business, data.question[:100] if data.question else None, "starter")
    return {"answer":engine_factory(get_settings()).ask(req,data.question)}

@app.post("/api/v1/analyses/{analysis_id}/work-orders", status_code=201)
def create_wo(analysis_id: str, request: Request, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    r=db.scalar(select(models.AnalysisRun).where(models.AnalysisRun.id==analysis_id,models.AnalysisRun.factory_id==identity.factory_id));
    if not r or not r.result_json: raise ValueError("analysis_not_ready")
    wdata=r.result_json.get("work_order") or {}; w=models.WorkOrder(factory_id=identity.factory_id,asset_id=r.asset_id,analysis_id=r.id,title=wdata.get("title","Maintenance"),description=r.result_json.get("recommendation",""),priority=r.priority or "medium",details_json=wdata); db.add(w); db.flush(); audit(db,identity,request.state.request_id,"work_order.created","work_order",w.id,after={"status":w.status}); db.commit(); db.refresh(w); return w
@app.get("/api/v1/work-orders")
def work_orders(db: Session=Depends(get_db), identity: Identity=Depends(get_identity)): return list(db.scalars(select(models.WorkOrder).where(models.WorkOrder.factory_id==identity.factory_id).order_by(models.WorkOrder.created_at.desc())))
def wo_transition(target, roles=None):
    """Route factory for a plain status change. `roles` gates who may do it."""
    def endpoint(order_id: str, request: Request, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
        w=db.scalar(select(models.WorkOrder).where(models.WorkOrder.id==order_id,models.WorkOrder.factory_id==identity.factory_id))
        if not w: raise ValueError("work_order_not_found")
        if roles: require_role(identity, roles)
        return transition(db,w,target,identity,request.state.request_id)
    return endpoint

# "AI mengusulkan dan menyiapkan; coordinator menyetujui; teknisi mengeksekusi;
# AI memverifikasi bukti." Only a coordinator may approve or reject, and a work
# order is not active until they do.
APPROVER_ROLES = ("manager", "admin")

@app.post("/api/v1/work-orders/{order_id}/submit")
def submit(order_id: str, request: Request, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    """Draft -> pending_approval. Puts the AI's proposal in front of a human."""
    return wo_transition("pending_approval")(order_id, request, db, identity)

@app.post("/api/v1/work-orders/{order_id}/approve")
def approve(order_id: str, request: Request, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    return wo_transition("approved", APPROVER_ROLES)(order_id, request, db, identity)

@app.post("/api/v1/work-orders/{order_id}/reject")
def reject(order_id: str, data: RejectIn, request: Request, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    w=db.scalar(select(models.WorkOrder).where(models.WorkOrder.id==order_id,models.WorkOrder.factory_id==identity.factory_id))
    if not w: raise ValueError("work_order_not_found")
    require_role(identity, APPROVER_ROLES)
    order = transition(db, w, "rejected", identity, request.state.request_id, reason=data.reason)
    return order

for _path,_target in (("schedule","scheduled"),("start","in_progress"),("block","blocked"),("complete","completed"),("cancel","cancelled")):
    app.add_api_route(f"/api/v1/work-orders/{{order_id}}/{_path}",wo_transition(_target),methods=["POST"])

@app.post("/api/v1/work-orders/{order_id}/progress")
def progress(order_id: str, data: ProgressIn, request: Request, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    """Records progress only. Completion goes through verification, not here."""
    w=db.scalar(select(models.WorkOrder).where(models.WorkOrder.id==order_id,models.WorkOrder.factory_id==identity.factory_id))
    if not w: raise ValueError("work_order_not_found")
    if w.status != "in_progress": raise ValueError(f"invalid_transition:{w.status}->in_progress")
    audit(db, identity, request.state.request_id, "work_order.progress_updated", "work_order", w.id,
          after={"percentage": data.percentage, "note": data.note})
    db.commit(); db.refresh(w)
    return {"id":w.id,"status":w.status,"percentage":data.percentage,"note":data.note}

@app.post("/api/v1/work-orders/{order_id}/result")
def submit_result(order_id: str, data: TechnicianResultIn, request: Request, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
    w = db.scalar(select(models.WorkOrder).where(models.WorkOrder.id == order_id, models.WorkOrder.factory_id == identity.factory_id))
    if not w: raise ValueError("work_order_not_found")
    require_role(identity, ("technician",))
    w = submit_technician_result(db, w, data, identity, request.state.request_id)
    return {"id": w.id, "status": w.status, "result": w.technician_result_json, "result_submitted_at": w.result_submitted_at}

@app.post("/api/v1/work-orders/{order_id}/verify")
def verify(order_id: str, request: Request, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
    w = db.scalar(select(models.WorkOrder).where(models.WorkOrder.id == order_id, models.WorkOrder.factory_id == identity.factory_id))
    if not w: raise ValueError("work_order_not_found")
    w = verify_work_order(db, w, identity, request.state.request_id, get_settings())
    return {"id": w.id, "status": w.status, "verification": w.verification_json, "verified_at": w.verified_at}

@app.get("/api/v1/work-orders/{order_id}/report")
def report(order_id: str, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
    w = db.scalar(select(models.WorkOrder).where(models.WorkOrder.id == order_id, models.WorkOrder.factory_id == identity.factory_id))
    if not w: raise ValueError("work_order_not_found")
    if not w.verification_json: raise ValueError("report_not_found")
    analysis = db.scalar(select(models.AnalysisRun).where(models.AnalysisRun.id == w.analysis_id, models.AnalysisRun.factory_id == identity.factory_id))
    asset = db.scalar(select(models.Asset).where(models.Asset.id == w.asset_id, models.Asset.factory_id == identity.factory_id))
    problem = (analysis.result_json or {}).get("recommendation", w.description) if analysis else w.description
    return {"work_order_id": w.id, "asset_id": w.asset_id, "problem": problem, "action": (w.technician_result_json or {}).get("work_done", ""), "findings": (w.technician_result_json or {}).get("findings", ""), "verdict": w.verification_json, "final_asset_state": {"status": asset.status if asset else None, "work_order_status": w.status}}

@app.get("/api/v1/work-orders/{order_id}/export")
def export_work_order(order_id: str, request: Request, format: str = Query("json", pattern="^(json|csv)$"), db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
    w = db.scalar(select(models.WorkOrder).where(models.WorkOrder.id == order_id, models.WorkOrder.factory_id == identity.factory_id))
    if not w: raise ValueError("work_order_not_found")
    erp_result = MockERP().push(w)
    audit(db, identity, request.state.request_id, "work_order.exported", "work_order", w.id,
          after={"format": format, "erp": erp_result})
    db.commit()
    analysis = db.scalar(select(models.AnalysisRun).where(models.AnalysisRun.id == w.analysis_id, models.AnalysisRun.factory_id == identity.factory_id))
    asset = db.scalar(select(models.Asset).where(models.Asset.id == w.asset_id, models.Asset.factory_id == identity.factory_id))
    report_data = None
    if w.verification_json:
        report_data = {"work_order_id": w.id, "asset_id": w.asset_id, "problem": (analysis.result_json or {}).get("recommendation", w.description) if analysis else w.description, "action": (w.technician_result_json or {}).get("work_done", ""), "findings": (w.technician_result_json or {}).get("findings", ""), "verdict": w.verification_json, "final_asset_state": {"status": asset.status if asset else None, "work_order_status": w.status}}
    if format == "json":
        return JSONResponse(content={"work_order": jsonable_encoder(w), "report": report_data}, headers={"Content-Disposition": f'attachment; filename="work-order-{w.id}.json"'})
    fields = ["work_order_id", "asset_id", "asset_name", "title", "description", "priority", "status", "action", "findings", "verdict"]
    row = {"work_order_id": w.id, "asset_id": w.asset_id, "asset_name": asset.name if asset else "", "title": w.title, "description": w.description, "priority": w.priority, "status": w.status, "action": (w.technician_result_json or {}).get("work_done", ""), "findings": (w.technician_result_json or {}).get("findings", ""), "verdict": json.dumps(w.verification_json or {}, ensure_ascii=True)}
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=fields); writer.writeheader(); writer.writerow(row)
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="work-order-{w.id}.csv"'})

@app.get("/api/v1/dashboard/summary")
def dashboard(db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    assets_n=db.scalar(select(func.count()).select_from(models.Asset).where(models.Asset.factory_id==identity.factory_id)); open_wo=db.scalar(select(func.count()).select_from(models.WorkOrder).where(models.WorkOrder.factory_id==identity.factory_id,models.WorkOrder.status.not_in(["completed","cancelled"]))); return {"assets":assets_n,"open_work_orders":open_wo,"analyses":db.scalar(select(func.count()).select_from(models.AnalysisRun).where(models.AnalysisRun.factory_id==identity.factory_id))}
@app.get("/api/v1/integrations/health")
def integrations(): return {"plc": "mock", "iot": "mock", "erp": MockERP().health_check()}

@app.exception_handler(ValueError)
async def value_error(request: Request, exc: ValueError):
    msg=str(exc); code="NOT_FOUND" if "not_found" in msg else "CONFLICT" if "transition" in msg or "conflicting" in msg else "VALIDATION_ERROR"; return error_response(request,code,msg,404 if code=="NOT_FOUND" else 409 if code=="CONFLICT" else 422)

@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    # One envelope for every error, including the ones FastAPI raises itself.
    code = {400: "VALIDATION_ERROR", 403: "FORBIDDEN", 404: "NOT_FOUND"}.get(exc.status_code, "ERROR")
    return error_response(request, code, str(exc.detail), exc.status_code)

@app.exception_handler(RequestValidationError)
async def request_validation_error(request: Request, exc: RequestValidationError):
    details = [{"field": ".".join(str(x) for x in item["loc"]), "reason": item["msg"]} for item in exc.errors()]
    return error_response(request, "VALIDATION_ERROR", "Input tidak valid", 422, details)
