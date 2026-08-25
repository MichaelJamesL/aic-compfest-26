import csv, io, json
from fastapi import Depends, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..work_orders.models import WorkOrder
from ..analysis.models import AnalysisRun
from ..assets.models import Asset
from ..auth import Identity, get_identity, require_role
from ..config import get_settings
from ..db import get_db
from ..repositories import audit
from ..work_orders.schemas import ProgressIn, RejectIn, ScheduleIn, TechnicianResultIn
from ..work_orders.service import transition, submit_technician_result, verify_work_order, apply_schedule
from . import scheduling


APPROVER_ROLES = ("manager", "admin")


def wo_transition(target, roles=None):
    def endpoint(order_id: str, request: Request, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        w = db.scalar(select(WorkOrder).where(WorkOrder.id == order_id, WorkOrder.factory_id == identity.factory_id))
        if not w: raise ValueError("work_order_not_found")
        if roles: require_role(identity, roles)
        return transition(db, w, target, identity, request.state.request_id)
    return endpoint


def register_routes(app):
    @app.post("/api/v1/analyses/{analysis_id}/work-orders", status_code=201)
    def create_wo(analysis_id: str, request: Request, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Create a work order from an analysis result."""
        r = db.scalar(select(AnalysisRun).where(AnalysisRun.id == analysis_id, AnalysisRun.factory_id == identity.factory_id))
        if not r or not r.result_json: raise ValueError("analysis_not_ready")
        wdata = r.result_json.get("work_order") or {}
        w = WorkOrder(
            factory_id=identity.factory_id, asset_id=r.asset_id, analysis_id=r.id,
            title=wdata.get("title", "Maintenance"),
            description=r.result_json.get("recommendation", ""),
            priority=r.priority or "medium", details_json=wdata,
        )
        db.add(w); db.flush()
        # Proposed now, not at approval: the coordinator reviews a concrete
        # technician and slot, and the slot is held against later work orders
        # from the moment it is proposed.
        proposal = scheduling.propose(db, identity.factory_id, wdata, w.priority)
        if proposal["technician"]:
            w.assigned_technician = proposal["technician"]
            w.scheduled_start, w.scheduled_end = proposal["start"], proposal["end"]
            w.schedule_note = "during_production" if proposal["during_production"] else None
        else:
            w.schedule_note = proposal["reason"]
        audit(db, identity, request.state.request_id, "work_order.created", "work_order", w.id,
              after={"status": w.status, "technician": w.assigned_technician,
                     "scheduled_start": w.scheduled_start.isoformat() if w.scheduled_start else None})
        db.commit(); db.refresh(w); return w

    @app.get("/api/v1/work-orders")
    def work_orders(db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """List all work orders for the authenticated factory."""
        return list(db.scalars(
            select(WorkOrder).where(WorkOrder.factory_id == identity.factory_id).order_by(WorkOrder.created_at.desc())
        ))

    @app.put("/api/v1/work-orders/{order_id}/assignment")
    def reschedule(order_id: str, data: ScheduleIn, request: Request, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Coordinator override of who does the job and when."""
        w = db.scalar(select(WorkOrder).where(WorkOrder.id == order_id, WorkOrder.factory_id == identity.factory_id))
        if not w: raise ValueError("work_order_not_found")
        require_role(identity, APPROVER_ROLES)
        return apply_schedule(db, w, data, identity, request.state.request_id)

    @app.post("/api/v1/work-orders/{order_id}/submit")
    def submit(order_id: str, request: Request, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Move a draft work order to pending_approval for coordinator review."""
        return wo_transition("pending_approval")(order_id, request, db, identity)

    @app.post("/api/v1/work-orders/{order_id}/approve")
    def approve(order_id: str, request: Request, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Approve a pending work order (coordinator/admin only)."""
        return wo_transition("approved", APPROVER_ROLES)(order_id, request, db, identity)

    @app.post("/api/v1/work-orders/{order_id}/reject")
    def reject(order_id: str, data: RejectIn, request: Request, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Reject a pending work order with a reason (coordinator/admin only)."""
        w = db.scalar(select(WorkOrder).where(WorkOrder.id == order_id, WorkOrder.factory_id == identity.factory_id))
        if not w: raise ValueError("work_order_not_found")
        require_role(identity, APPROVER_ROLES)
        order = transition(db, w, "rejected", identity, request.state.request_id, reason=data.reason)
        return order

    for _path, _target in (("schedule", "scheduled"), ("start", "in_progress"), ("block", "blocked"), ("complete", "completed"), ("cancel", "cancelled")):
        app.add_api_route(f"/api/v1/work-orders/{{order_id}}/{_path}", wo_transition(_target), methods=["POST"])

    @app.post("/api/v1/work-orders/{order_id}/progress")
    def progress(order_id: str, data: ProgressIn, request: Request, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Record progress percentage on an in-progress work order."""
        w = db.scalar(select(WorkOrder).where(WorkOrder.id == order_id, WorkOrder.factory_id == identity.factory_id))
        if not w: raise ValueError("work_order_not_found")
        if w.status != "in_progress": raise ValueError(f"invalid_transition:{w.status}->in_progress")
        audit(db, identity, request.state.request_id, "work_order.progress_updated", "work_order", w.id, after={"percentage": data.percentage, "note": data.note})
        db.commit(); db.refresh(w)
        return {"id": w.id, "status": w.status, "percentage": data.percentage, "note": data.note}

    @app.post("/api/v1/work-orders/{order_id}/result")
    def submit_result(order_id: str, data: TechnicianResultIn, request: Request, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Technician submits work results and findings."""
        w = db.scalar(select(WorkOrder).where(WorkOrder.id == order_id, WorkOrder.factory_id == identity.factory_id))
        if not w: raise ValueError("work_order_not_found")
        require_role(identity, ("technician",))
        w = submit_technician_result(db, w, data, identity, request.state.request_id)
        return {"id": w.id, "status": w.status, "result": w.technician_result_json, "result_submitted_at": w.result_submitted_at}

    @app.post("/api/v1/work-orders/{order_id}/verify")
    def verify(order_id: str, request: Request, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """AI verifies technician work results against expectations."""
        w = db.scalar(select(WorkOrder).where(WorkOrder.id == order_id, WorkOrder.factory_id == identity.factory_id))
        if not w: raise ValueError("work_order_not_found")
        w = verify_work_order(db, w, identity, request.state.request_id, get_settings())
        return {"id": w.id, "status": w.status, "verification": w.verification_json, "verified_at": w.verified_at}

    @app.get("/api/v1/work-orders/{order_id}/report")
    def report(order_id: str, db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Return the final maintenance report for a completed work order."""
        w = db.scalar(select(WorkOrder).where(WorkOrder.id == order_id, WorkOrder.factory_id == identity.factory_id))
        if not w: raise ValueError("work_order_not_found")
        if not w.verification_json: raise ValueError("report_not_found")
        analysis = db.scalar(select(AnalysisRun).where(AnalysisRun.id == w.analysis_id, AnalysisRun.factory_id == identity.factory_id))
        asset = db.scalar(select(Asset).where(Asset.id == w.asset_id, Asset.factory_id == identity.factory_id))
        problem = (analysis.result_json or {}).get("recommendation", w.description) if analysis else w.description
        return {
            "work_order_id": w.id, "asset_id": w.asset_id, "problem": problem,
            "action": (w.technician_result_json or {}).get("work_done", ""),
            "findings": (w.technician_result_json or {}).get("findings", ""),
            "verdict": w.verification_json,
            "final_asset_state": {"status": asset.status if asset else None, "work_order_status": w.status},
        }

    @app.get("/api/v1/work-orders/{order_id}/export")
    def export_work_order(order_id: str, request: Request, format: str = Query("json", pattern="^(json|csv)$"), db: Session = Depends(get_db), identity: Identity = Depends(get_identity)):
        """Export a work order as JSON or CSV with ERP push."""
        w = db.scalar(select(WorkOrder).where(WorkOrder.id == order_id, WorkOrder.factory_id == identity.factory_id))
        if not w: raise ValueError("work_order_not_found")
        from ..adapters import MockERP
        erp_result = MockERP().push(w)
        audit(db, identity, request.state.request_id, "work_order.exported", "work_order", w.id, after={"format": format, "erp": erp_result})
        db.commit()
        analysis = db.scalar(select(AnalysisRun).where(AnalysisRun.id == w.analysis_id, AnalysisRun.factory_id == identity.factory_id))
        asset = db.scalar(select(Asset).where(Asset.id == w.asset_id, Asset.factory_id == identity.factory_id))
        report_data = None
        if w.verification_json:
            report_data = {
                "work_order_id": w.id, "asset_id": w.asset_id,
                "problem": (analysis.result_json or {}).get("recommendation", w.description) if analysis else w.description,
                "action": (w.technician_result_json or {}).get("work_done", ""),
                "findings": (w.technician_result_json or {}).get("findings", ""),
                "verdict": w.verification_json,
                "final_asset_state": {"status": asset.status if asset else None, "work_order_status": w.status},
            }
        if format == "json":
            return JSONResponse(
                content={"work_order": jsonable_encoder(w), "report": report_data},
                headers={"Content-Disposition": f'attachment; filename="work-order-{w.id}.json"'},
            )
        fields = ["work_order_id", "asset_id", "asset_name", "title", "description", "priority", "status", "action", "findings", "verdict"]
        row = {
            "work_order_id": w.id, "asset_id": w.asset_id,
            "asset_name": asset.name if asset else "", "title": w.title,
            "description": w.description, "priority": w.priority, "status": w.status,
            "action": (w.technician_result_json or {}).get("work_done", ""),
            "findings": (w.technician_result_json or {}).get("findings", ""),
            "verdict": json.dumps(w.verification_json or {}, ensure_ascii=True),
        }
        output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=fields); writer.writeheader(); writer.writerow(row)
        return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="work-order-{w.id}.csv"'})