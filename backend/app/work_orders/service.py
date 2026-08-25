from datetime import datetime, timezone

from sqlalchemy import select

from ..analysis import service as _analysis
from ..documents.models import Document
from ..maintenance.models import MaintenanceRecord
from ..repositories import audit
from .schemas import VerificationResultOut
from ..work_orders.models import WorkOrder
from . import scheduling

TRANSITIONS = {
    "draft": {"pending_approval", "cancelled"},
    "pending_approval": {"approved", "rejected", "cancelled"},
    "approved": {"scheduled", "cancelled"},
    "scheduled": {"in_progress", "cancelled"},
    "in_progress": {"blocked", "cancelled"},
    "blocked": {"in_progress", "cancelled"},
    "completed": set(),
    "cancelled": set(),
    "rejected": set(),
}


def transition(db, order, target, identity, request_id, reason: str | None = None):
    if target not in TRANSITIONS.get(order.status, set()):
        raise ValueError(f"invalid_transition:{order.status}->{target}")
    before = {"status": order.status}
    order.status = target
    after = {"status": target}
    if reason:
        after["reason"] = reason
        details = dict(order.details_json or {})
        details["rejection_reason"] = reason
        order.details_json = details
    audit(db, identity, request_id, "work_order.status_changed", "work_order", order.id, before, after)
    db.commit()
    db.refresh(order)
    return order


def report_was_rejected(order) -> bool:
    """A verdict that is not `resolved` sends the job back to the technician."""
    return bool(order.verification_json) and order.verification_json.get("verdict") != "resolved"


def submit_technician_result(db, order, payload, identity, request_id):
    result = payload.model_dump(mode="json")
    if order.technician_result_json is not None:
        if order.technician_result_json == result:
            return order
        if not report_was_rejected(order):
            # Write-once while the report still stands: a coordinator verifies
            # against the evidence submitted, so it cannot change underneath them.
            raise ValueError("conflicting_technician_result")
        # Rejected: the technician redoes the work and reports again. Keep the
        # rejected attempt — it is the record of what was tried and why it failed
        # — and clear the verdict so verification runs fresh on the new evidence.
        details = dict(order.details_json or {})
        details.setdefault("result_attempts", []).append({
            "result": order.technician_result_json,
            "verification": order.verification_json,
            "submitted_at": order.result_submitted_at.isoformat() if order.result_submitted_at else None,
            "verified_at": order.verified_at.isoformat() if order.verified_at else None,
        })
        order.details_json = details
        order.verification_json = None
        order.verified_at = None
        audit(db, identity, request_id, "work_order.result_resubmitted", "work_order", order.id,
              before={"attempt": len(details["result_attempts"])}, after={"result": result})
    if order.status != "in_progress":
        raise ValueError(f"invalid_transition:{order.status}->result")
    order.technician_result_json = result
    order.result_submitted_at = datetime.now(timezone.utc)
    audit(db, identity, request_id, "work_order.result_submitted", "work_order", order.id, after={"status": order.status, "result": result})
    db.commit()
    db.refresh(order)
    return order


def verify_work_order(db, order, identity, request_id, settings):
    if order.verification_json is not None:
        if order.status == "completed" and (order.verification_json.get("ingestion") or {}).get("status") != "ready":
            document = db.scalar(select(Document).where(
                Document.factory_id == order.factory_id,
                Document.storage_key == f"generated/{order.factory_id}/{order.id}.txt",
            ))
            if document:
                _finish_history_ingestion(db, document, order, settings)
        return order
    if order.status != "in_progress":
        raise ValueError(f"invalid_transition:{order.status}->verification")
    if order.technician_result_json is None:
        raise ValueError("technician_result_required")
    try:
        from src import TechnicianResult, VerificationResult, WorkOrder as EngineWorkOrder
        technician_result = TechnicianResult(**order.technician_result_json)
        work_order = EngineWorkOrder(
            title=order.title,
            steps=(order.details_json or {}).get("steps", []),
            parts=(order.details_json or {}).get("parts", []),
            est_duration_h=(order.details_json or {}).get("est_duration_h"),
            required_skills=(order.details_json or {}).get("required_skills", []),
            safety_notes=(order.details_json or {}).get("safety_notes", []),
        )
    except (ImportError, ModuleNotFoundError):
        technician_result = order.technician_result_json
        work_order = order
    try:
        verification = _analysis.engine_factory(settings).verify(work_order, technician_result)
    except Exception as exc:
        raise ValueError("verification_failed") from exc
    if hasattr(verification, "model_dump"):
        verification = verification.model_dump(mode="json")
    verification = VerificationResultOut(**verification).model_dump(mode="json")
    order.verification_json = verification
    order.verified_at = datetime.now(timezone.utc)
    audit(db, identity, request_id, "work_order.verification_completed", "work_order", order.id, after=verification)
    if verification["verdict"] == "resolved":
        before = order.status
        order.status = "completed"
        audit(db, identity, request_id, "work_order.status_changed", "work_order", order.id, before={"status": before}, after={"status": "completed"})
        record = MaintenanceRecord(
            factory_id=order.factory_id,
            asset_id=order.asset_id,
            performed_at=order.verified_at,
            action=order.technician_result_json.get("work_done", ""),
            findings=order.technician_result_json.get("findings", ""),
            parts_used_json=order.technician_result_json.get("parts_used", []),
            source="work_order_verification",
        )
        db.add(record)
        db.flush()
        ingestion = {"status": "not_attempted", "error": None}
        text = f"Performed at: {record.performed_at.isoformat()}\nAction: {record.action}\nFindings: {record.findings}\nParts: {', '.join(record.parts_used_json or [])}"
        document = Document(
            factory_id=record.factory_id,
            asset_id=record.asset_id,
            title=f"Maintenance history {order.id}",
            kind="maintenance_history",
            filename=f"maintenance-{record.id}.txt",
            mime_type="text/plain",
            size_bytes=len(text.encode("utf-8")),
            storage_key=f"generated/{record.factory_id}/{order.id}.txt",
            extracted_text=text,
            ingestion_status="pending",
        )
        db.add(document)
        db.flush()
        verification = {**verification, "ingestion": ingestion}
        order.verification_json = verification
    db.commit()
    db.refresh(order)
    if verification.get("verdict") == "resolved":
        document = db.scalar(select(Document).where(
            Document.factory_id == order.factory_id,
            Document.storage_key == f"generated/{order.factory_id}/{order.id}.txt",
        ))
        if document:
            _finish_history_ingestion(db, document, order, settings)
            db.refresh(order)
    return order


def _finish_history_ingestion(db, document, order, settings):
    ingestion = {"status": "failed", "error": None}
    try:
        from src import Document as EngineDocument, knowledge
        knowledge.ingest(
            EngineDocument(id=document.id, title=document.title, kind=document.kind,
                           text=document.extracted_text, factory_id=document.factory_id),
            asset_id=order.asset_id,
            factory_id=order.factory_id,
        )
        ingestion = {"status": "ready", "error": None}
        document.ingestion_status = "ready"
        document.ingestion_error = None
    except Exception as exc:
        ingestion["error"] = str(exc)[:500]
        document.ingestion_status = "failed"
        document.ingestion_error = ingestion["error"]
    order.verification_json = {**(order.verification_json or {}), "ingestion": ingestion}
    db.commit()

def apply_schedule(db, order, data, identity, request_id):
    """Move a job to another technician or another slot.

    A technician is never double-booked: the clashing work order is named so the
    coordinator can pick around it. Booking outside a shift or into production
    hours is allowed and only noted — the coordinator may know something the
    roster does not.
    """
    if order.status in scheduling.RELEASED:
        raise ValueError(f"invalid_transition:{order.status}->schedule")
    clash = scheduling.conflicting_order(
        db, order.factory_id, data.technician, data.start, data.end, exclude_order_id=order.id
    )
    if clash:
        raise ValueError(
            f"technician_double_booked:{clash.title} "
            f"({clash.scheduled_start:%d %b %H:%M}-{clash.scheduled_end:%H:%M})"
        )
    before = {"technician": order.assigned_technician,
              "start": order.scheduled_start.isoformat() if order.scheduled_start else None}
    order.assigned_technician = data.technician
    order.scheduled_start, order.scheduled_end = data.start, data.end
    order.schedule_note = "manual"
    audit(db, identity, request_id, "work_order.rescheduled", "work_order", order.id, before,
          {"technician": data.technician, "start": data.start.isoformat(), "end": data.end.isoformat()})
    db.commit()
    db.refresh(order)
    return order
