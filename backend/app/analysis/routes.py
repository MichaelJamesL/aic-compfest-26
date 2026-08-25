from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import Depends, Request
from ..analysis.models import AnalysisRun
from ..assets.service import get_asset
from ..auth import Identity, get_identity
from ..config import get_settings
from ..db import get_db
from .schemas import AnalysisIn, AskIn
from .service import _inventory_for_asset, engine_factory, engine_request, input_disclosure, run_analysis


def analysis_response(run, include_snapshot=False):
    response = {
        "id": run.id, "status": run.status, "result": run.result_json,
        "input_disclosure": input_disclosure(run.request_snapshot_json),
        "engine_mode": run.engine_mode, "error": run.error_message,
        "error_code": run.error_code, "error_message": run.error_message,
        "health_score": run.health_score, "priority": run.priority,
    }
    if include_snapshot:
        response["request_snapshot"] = run.request_snapshot_json
    return response


def register_routes(app):
    @app.post("/api/v1/assets/{asset_id}/analyses", status_code=201)
    def analyze(asset_id: str, data: AnalysisIn, request: Request, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Run the AI maintenance analysis engine on an asset."""
        a = get_asset(db, asset_id, identity)
        run = run_analysis(db, a, data, identity, request.state.request_id, get_settings())
        return analysis_response(run)

    @app.get("/api/v1/analyses/{analysis_id}")
    def analysis(analysis_id: str, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Return a single analysis run with its full request snapshot."""
        r = db.scalar(select(AnalysisRun).where(AnalysisRun.id == analysis_id, AnalysisRun.factory_id == identity.factory_id))
        if not r: raise ValueError("analysis_not_found")
        return analysis_response(r, include_snapshot=True)

    @app.get("/api/v1/assets/{asset_id}/analyses")
    def analysis_history(asset_id: str, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """List all analysis runs for an asset, newest first."""
        get_asset(db, asset_id, identity)
        return list(db.scalars(
            select(AnalysisRun).where(AnalysisRun.asset_id == asset_id).order_by(AnalysisRun.created_at.desc())
        ))

    @app.post("/api/v1/assets/{asset_id}/ask")
    def ask(asset_id: str, data: AskIn, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Ask the AI maintenance engine a free-text question about an asset."""
        from ..assets.models import BusinessContext
        from ..readings.models import Reading
        from ..maintenance.models import MaintenanceRecord
        a = get_asset(db, asset_id, identity)
        readings = list(db.scalars(select(Reading).where(Reading.asset_id == a.id).order_by(Reading.recorded_at.desc()).limit(50)))
        history = list(db.scalars(select(MaintenanceRecord).where(MaintenanceRecord.asset_id == a.id).order_by(MaintenanceRecord.performed_at.desc()).limit(10)))
        context = db.get(BusinessContext, identity.factory_id)
        business = {
            "production_schedule": context.production_schedule if context else None,
            "inventory": _inventory_for_asset(db, a),
            "technicians": context.technicians_json if context else [],
            "operator_report": a.operator_report,
        }
        req = engine_request(a, readings, history, business, data.question[:100] if data.question else None, "starter")
        return {"answer": engine_factory(get_settings()).ask(req, data.question)}