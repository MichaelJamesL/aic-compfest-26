from contextlib import asynccontextmanager
import re
from datetime import datetime, timezone
from pathlib import Path
import csv, io, json, uuid
from fastapi import Depends, FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from . import models
from .auth import Identity, get_identity, require_role
from .config import get_settings
from .db import get_db, init_db
from .errors import error_response
from .repositories import audit, one_or_404
from .schemas import *
from .services import run_analysis, transition
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
    request.state.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request); response.headers["X-Request-ID"] = request.state.request_id; return response

def _factory_storage_key(factory_id: str) -> str:
    """Safe storage-key prefix. Rejects anything that could escape the root."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", factory_id):
        raise ValueError("invalid_factory_id")
    return factory_id[:8]

def get_asset(db, asset_id, identity):
    try: return one_or_404(db, models.Asset, asset_id, identity.factory_id)
    except ValueError: raise ValueError("asset_not_found")

@app.get("/health/live")
def live(): return {"status": "ok"}
@app.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    try: db.execute(select(func.count()).select_from(models.Factory)); return {"status": "ready", "database": "ok", "storage": "ok"}
    except Exception: return JSONResponse(status_code=503, content={"status": "not_ready", "database": "error"})
@app.get("/config/capabilities")
def capabilities():
    s=get_settings(); return {"tier": s.deployment_tier, "capabilities": {"assets": True, "documents": True, "analysis": True, "work_orders": True, "mock_plc": True, "ai_engine": s.ai_engine_enabled}}

@app.get("/api/v1/assets", response_model=list[AssetOut])
def assets(db: Session=Depends(get_db), identity: Identity=Depends(get_identity)): return list(db.scalars(select(models.Asset).where(models.Asset.factory_id==identity.factory_id).order_by(models.Asset.name)))
@app.post("/api/v1/assets", response_model=AssetOut, status_code=201)
def create_asset(data: AssetIn, request: Request, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    a=models.Asset(factory_id=identity.factory_id, name=data.name, asset_type=data.asset_type, criticality=data.criticality, location=data.location, specs_json=data.specs_json); db.add(a); db.flush(); audit(db,identity,request.state.request_id,"asset.created","asset",a.id,after={"name":a.name}); db.commit(); db.refresh(a); return a
@app.get("/api/v1/assets/{asset_id}", response_model=AssetOut)
def asset_detail(asset_id: str, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)): return get_asset(db,asset_id,identity)
@app.patch("/api/v1/assets/{asset_id}", response_model=AssetOut)
def update_asset(asset_id: str, data: AssetIn, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    a=get_asset(db,asset_id,identity); a.name=data.name; a.asset_type=data.asset_type; a.criticality=data.criticality; a.location=data.location; a.specs_json=data.specs_json; db.commit(); db.refresh(a); return a
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".pdf"}

def _check_file(file: UploadFile, max_size: int = MAX_UPLOAD_SIZE) -> None:
    if not file.filename: raise ValueError("empty_filename")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS: raise ValueError(f"unsupported_extension:{ext}")
    # Read a preview to check content-type; limit read to 4KB
    preview = file.file.read(4096)
    file.file.seek(0)
    if not (file.content_type or "").startswith("text/") and not ext in {".csv", ".json"}:
        # Try to decode as text; if fail, reject for non-text uploads in Starter
        try: preview.decode("utf-8")
        except UnicodeDecodeError: raise ValueError("non_text_file")

@app.post("/api/v1/assets/import")
async def import_assets(file: UploadFile=File(...), db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    _check_file(file)
    raw=await file.read(); 
    if len(raw) > MAX_UPLOAD_SIZE: raise ValueError("file_too_large")
    rows=json.loads(raw) if file.filename.endswith(".json") else list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    created=[]; errors=[]
    for i, row in enumerate(rows):
        try:
            name = row.get("name", "").strip()
            if not name: errors.append({"row": i, "reason": "missing_name"}); continue
            a=models.Asset(factory_id=identity.factory_id,name=name,asset_type=row.get("asset_type","machine"),criticality=row.get("criticality","medium"),specs_json={})
            # Idempotent by external_id if provided
            ext_id = row.get("external_id")
            if ext_id:
                existing = db.scalar(select(models.Asset).where(models.Asset.factory_id==identity.factory_id, models.Asset.external_id==ext_id))
                if existing: 
                    errors.append({"row": i, "reason": "duplicate_external_id", "id": existing.id}); continue
                a.external_id = ext_id
            db.add(a); created.append(a)
        except Exception as e:
            errors.append({"row": i, "reason": str(e)})
    db.commit(); return {"imported":len(created), "errors": errors}

@app.post("/api/v1/knowledge/documents", response_model=DocumentOut, status_code=201)
async def document(file: UploadFile=File(...), kind: str="sop", asset_id: str|None=None, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    _check_file(file)
    raw=await file.read(); 
    if len(raw) > MAX_UPLOAD_SIZE: raise ValueError("file_too_large")
    safe_key=_factory_storage_key(identity.factory_id); key=f"{safe_key}/{uuid.uuid4()}-{Path(file.filename or 'upload').name}"; path=get_settings().storage_path/key; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(raw)
    text=raw.decode("utf-8",errors="replace") if (file.content_type or "").startswith("text/") or (file.filename or "").endswith((".txt",".md",".csv",".json")) else ""
    d=models.Document(factory_id=identity.factory_id,asset_id=asset_id,title=file.filename or "document",kind=kind,filename=file.filename or "document",mime_type=file.content_type or "application/octet-stream",size_bytes=len(raw),storage_key=str(key),extracted_text=text,ingestion_status="pending"); db.add(d); db.commit(); db.refresh(d); return d
@app.post("/api/v1/assets/{asset_id}/readings")
def reading(asset_id: str, data: ReadingIn, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    a=get_asset(db,asset_id,identity)
    existing = db.scalar(select(models.Reading).where(
        models.Reading.factory_id==identity.factory_id,
        models.Reading.asset_id==a.id,
        models.Reading.external_id==data.external_id
    ))
    if existing: return {"id":existing.id,"quality":existing.quality}
    r=models.Reading(factory_id=identity.factory_id,asset_id=a.id,tag=data.tag,value=data.value,unit=data.unit,recorded_at=data.recorded_at,source=data.source,external_id=data.external_id); db.add(r); db.commit(); return {"id":r.id,"quality":r.quality}
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
    a=get_asset(db,asset_id,identity); r=models.MaintenanceRecord(factory_id=identity.factory_id,asset_id=a.id,performed_at=data.performed_at,action=data.action,findings=data.findings,parts_used_json=data.parts_used); db.add(r); db.commit(); return {"id":r.id}


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
        knowledge.ingest(EngineDocument(id=d.id, title=d.title, kind=d.kind, text=d.extracted_text), asset_id=d.asset_id)
    except Exception as exc:
        d.ingestion_status="failed"; d.ingestion_error=str(exc)[:500]
    else:
        d.ingestion_status="ready"; d.ingestion_error=None
    db.commit(); db.refresh(d); return d

@app.get("/api/v1/knowledge/documents", response_model=list[DocumentOut])
def documents(db: Session=Depends(get_db), identity: Identity=Depends(get_identity)): return list(db.scalars(select(models.Document).where(models.Document.factory_id==identity.factory_id,models.Document.status=="active")))

@app.post("/api/v1/assets/{asset_id}/analyses", status_code=201)
def analyze(asset_id: str, data: AnalysisIn, request: Request, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    a=get_asset(db,asset_id,identity); run=run_analysis(db,a,data,identity,request.state.request_id,get_settings()); return {"id":run.id,"status":run.status,"result":run.result_json,"engine_mode":run.engine_mode,"error_code":run.error_code,"error_message":run.error_message,"health_score":run.health_score,"priority":run.priority}
@app.get("/api/v1/analyses/{analysis_id}")
def analysis(analysis_id: str, db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    r=db.scalar(select(models.AnalysisRun).where(models.AnalysisRun.id==analysis_id,models.AnalysisRun.factory_id==identity.factory_id));
    if not r: raise ValueError("analysis_not_found")
    return {"id":r.id,"status":r.status,"result":r.result_json,"request_snapshot":r.request_snapshot_json,"error":r.error_message,"engine_mode":r.engine_mode,"error_code":r.error_code}
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

@app.get("/api/v1/dashboard/summary")
def dashboard(db: Session=Depends(get_db), identity: Identity=Depends(get_identity)):
    assets_n=db.scalar(select(func.count()).select_from(models.Asset).where(models.Asset.factory_id==identity.factory_id)); open_wo=db.scalar(select(func.count()).select_from(models.WorkOrder).where(models.WorkOrder.factory_id==identity.factory_id,models.WorkOrder.status.not_in(["completed","cancelled"]))); return {"assets":assets_n,"open_work_orders":open_wo,"analyses":db.scalar(select(func.count()).select_from(models.AnalysisRun).where(models.AnalysisRun.factory_id==identity.factory_id))}
@app.get("/api/v1/integrations/health")
def integrations(): return {"plc": "mock", "iot": "mock", "erp": MockERP().health_check()}

@app.exception_handler(ValueError)
async def value_error(request: Request, exc: ValueError):
    msg=str(exc); code="NOT_FOUND" if "not_found" in msg else "CONFLICT" if "transition" in msg else "VALIDATION_ERROR"; return error_response(request,code,msg,404 if code=="NOT_FOUND" else 409 if code=="CONFLICT" else 422)

@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    # One envelope for every error, including the ones FastAPI raises itself.
    code = {400: "VALIDATION_ERROR", 403: "FORBIDDEN", 404: "NOT_FOUND"}.get(exc.status_code, "ERROR")
    return error_response(request, code, str(exc.detail), exc.status_code)

@app.exception_handler(RequestValidationError)
async def request_validation_error(request: Request, exc: RequestValidationError):
    details = [{"field": ".".join(str(x) for x in item["loc"]), "reason": item["msg"]} for item in exc.errors()]
    return error_response(request, "VALIDATION_ERROR", "Input tidak valid", 422, details)
