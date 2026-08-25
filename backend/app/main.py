from contextlib import asynccontextmanager
import uuid
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .db import get_db, init_db
from .config import get_settings
from .errors import error_response
from .auth import Identity, get_identity
from .assets.models import Asset, Factory
from .work_orders.models import WorkOrder
from .analysis.models import AnalysisRun
from .adapters import MockPLC, MockIoT, MockERP
from .readings.schemas import ReadingIn
from .readings.service import persist_reading
from .assets.service import get_asset


@asynccontextmanager
async def lifespan(app):
    init_db()
    get_settings().storage_path.mkdir(parents=True, exist_ok=True)
    with next(get_db()) as db:
        if not db.get(Factory, "demo-factory"):
            db.add(Factory(id="demo-factory", name="Demo Factory", deployment_tier=get_settings().deployment_tier))
            db.commit()
    yield


app = FastAPI(title="AIC Predictive Maintenance Backend", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def request_id(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:36]
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


from .health.routes import register_routes as register_health
from .assets.routes import register_routes as register_assets
from .readings.routes import register_routes as register_readings
from .maintenance.routes import register_routes as register_maintenance
from .documents.routes import register_routes as register_documents
from .qc.routes import register_routes as register_qc
from .analysis.routes import register_routes as register_analysis
from .work_orders.routes import register_routes as register_work_orders

register_health(app)
register_assets(app)
register_readings(app)
register_maintenance(app)
register_documents(app)
register_qc(app)
register_analysis(app)
register_work_orders(app)


@app.get("/api/v1/dashboard/summary")
def dashboard(db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
    """Return aggregate counts for assets, open work orders, and analyses."""
    assets_n = db.scalar(select(func.count()).select_from(Asset).where(Asset.factory_id == identity.factory_id))
    open_wo = db.scalar(select(func.count()).select_from(WorkOrder).where(WorkOrder.factory_id == identity.factory_id, WorkOrder.status.not_in(["completed", "cancelled"])))
    return {
        "assets": assets_n, "open_work_orders": open_wo,
        "analyses": db.scalar(select(func.count()).select_from(AnalysisRun).where(AnalysisRun.factory_id == identity.factory_id)),
    }


@app.get("/api/v1/integrations/health")
def integrations():
    """Return mock health status for PLC, IoT, and ERP integrations."""
    return {"plc": "mock", "iot": "mock", "erp": MockERP().health_check()}


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
    """Pull simulated PLC sensor data for an asset."""
    return ingest_mock(asset_id, MockPLC(), db, identity)


@app.post("/api/v1/assets/{asset_id}/ingest/iot")
def ingest_iot(asset_id: str, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
    """Pull simulated IoT sensor data for an asset."""
    return ingest_mock(asset_id, MockIoT(), db, identity)


@app.exception_handler(ValueError)
async def value_error(request: Request, exc: ValueError):
    msg = str(exc)
    conflict = any(token in msg for token in ("transition", "conflicting", "double_booked"))
    code = "NOT_FOUND" if "not_found" in msg else "CONFLICT" if conflict else "VALIDATION_ERROR"
    return error_response(request, code, msg, 404 if code == "NOT_FOUND" else 409 if code == "CONFLICT" else 422)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    code = {400: "VALIDATION_ERROR", 403: "FORBIDDEN", 404: "NOT_FOUND"}.get(exc.status_code, "ERROR")
    return error_response(request, code, str(exc.detail), exc.status_code)


@app.exception_handler(RequestValidationError)
async def request_validation_error(request: Request, exc: RequestValidationError):
    details = [{"field": ".".join(str(x) for x in item["loc"]), "reason": item["msg"]} for item in exc.errors()]
    return error_response(request, "VALIDATION_ERROR", "Input tidak valid", 422, details)