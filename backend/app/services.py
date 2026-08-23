from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import floor
from pathlib import Path
import json, csv, io, uuid
from types import SimpleNamespace
from . import models
from .repositories import one_or_404, audit
from .schemas import VerificationResultOut
from sqlalchemy import select


_OFFLINE_IQR_K = 1.5
_OFFLINE_WEIGHTS = {"low": 5, "medium": 10, "high": 20, "critical": 30}


class _OfflineAnomaly:
    def __init__(self, tag, observed, expected_range, severity):
        self.tag = tag
        self.observed = observed
        self.expected_range = expected_range
        self.severity = severity

    def model_dump(self, mode="json"):
        return {
            "tag": self.tag,
            "observed": self.observed,
            "expected_range": self.expected_range,
            "severity": self.severity,
            "method": "iqr",
        }


def _offline_percentile(values, fraction):
    position = (len(values) - 1) * fraction
    lower = floor(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def _offline_signals(readings, history, asset, now=None):
    """Small stdlib-only signal path for backend-only installs."""
    grouped = defaultdict(list)
    for reading in readings:
        grouped[reading.tag].append(float(reading.value))

    anomalies = []
    for tag, values in grouped.items():
        if len(values) < 8:
            continue
        ordered = sorted(values)
        q1 = _offline_percentile(ordered, 0.25)
        q3 = _offline_percentile(ordered, 0.75)
        iqr = q3 - q1
        lower, upper = q1 - _OFFLINE_IQR_K * iqr, q3 + _OFFLINE_IQR_K * iqr
        candidates = [value for value in values if value < lower or value > upper]
        if not candidates:
            continue
        observed = max(candidates, key=lambda value: max(lower - value, value - upper))
        margin = max(lower - observed, observed - upper)
        width = upper - lower
        multiple = margin / (width / 2) if width else 0
        severity = "critical" if multiple > 2 else "high" if multiple > 1.5 else "medium" if multiple > 1 else "low"
        anomalies.append(_OfflineAnomaly(tag, round(observed, 2), (round(lower, 2), round(upper, 2)), severity))

    score = 100
    reasons = []
    for anomaly in anomalies:
        score -= _OFFLINE_WEIGHTS[anomaly.severity]
        reasons.append(f"{anomaly.tag} anomaly ({anomaly.severity})")

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    interval = int((getattr(asset, "specs", {}) or {}).get("maintenance_interval_days", 90))
    if history:
        last = max(history, key=lambda record: record.performed_at).performed_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        elapsed = (now - last.astimezone(timezone.utc)).total_seconds() / 86400
        if elapsed > interval:
            score -= 10
            reasons.append(f"maintenance overdue by {elapsed - interval:.0f}d")
    cutoff = now - timedelta(days=30)
    failures = defaultdict(int)
    for record in history:
        performed_at = record.performed_at
        if performed_at.tzinfo is None:
            performed_at = performed_at.replace(tzinfo=timezone.utc)
        if performed_at.astimezone(timezone.utc) >= cutoff and record.asset_id == asset.id:
            failures[getattr(record, "findings", "") or record.action] += 1
    for count in failures.values():
        if count > 1:
            score -= 5 * (count - 1)
            reasons.append(f"repeat failure x{count}")

    score = max(0, min(100, score))
    summary = "Asset operating within normal parameters." if score >= 80 else "Minor concerns; schedule inspection." if score >= 60 else "Significant degradation; plan maintenance soon." if score >= 40 else "Critical condition; intervene immediately."
    if reasons:
        summary += " " + "; ".join(reasons) + "."
    return anomalies, score, summary


class StubEngine:
    """Offline engine with the same useful output shape as ai-engine."""
    def analyze(self, request):
        # Keep the AI package out of backend import time. These pure functions
        # are all the offline engine needs for deterministic numeric signals.
        try:
            from src.signals import detect_anomalies, health_score
        except ImportError:
            # The documented backend-only test/install command has no AI extra.
            # Keep that deployment usable; the bundled engine path above is used
            # whenever ai-engine is installed (as it is in the application image).
            def detect_anomalies(readings):
                return _offline_signals(readings, history, signal_asset)[0]

            def health_score(asset, anomalies, history):
                return _offline_signals(readings, history, asset)[1:]

        asset = getattr(request, "asset", None)
        signal_asset = SimpleNamespace(
            id=getattr(asset, "id", "offline-asset"),
            specs=getattr(asset, "specs", getattr(asset, "specs_json", {})) or {},
        )
        readings = list(getattr(request, "readings", []))
        history = list(getattr(request, "history", []))
        anomalies = detect_anomalies(readings)
        score, summary = health_score(signal_asset, anomalies, history)
        priority = "critical" if score < 40 else "high" if score < 65 else "medium" if score < 85 else "low"
        condition = getattr(request, "manual_condition", None)
        return {"health_score": score, "health_summary": summary, "anomalies": [a.model_dump(mode="json") for a in anomalies], "defects": [], "root_causes": [{"cause": "Condition requires inspection" if condition else "No significant signal", "confidence": 0.55, "evidence": [condition] if condition else []}], "recommendation": "Inspect and schedule preventive maintenance" if priority != "low" else "Continue monitoring", "priority": priority, "recommended_window": "Next available maintenance window", "explanation": "Generated by offline Starter engine stub", "blockers": [], "work_order": {"title": "Inspect asset", "steps": ["Inspect machine condition", "Verify readings"], "parts": [], "est_duration_h": 2, "required_skills": ["maintenance"], "safety_notes": ["Apply lockout/tagout"]}, "tier": request.tier.value, "model": "offline-stub", "sources": []}
    mode = "offline_stub"
    def ask(self, request, question): return f"Offline Starter answer for '{question}': review the asset condition and applicable SOP."
    def verify(self, work_order, technician_result):
        result = technician_result if isinstance(technician_result, dict) else technician_result.model_dump()
        if result.get("work_done") and result.get("findings"):
            return {"verdict": "resolved", "evidence": result.get("evidence", []), "follow_up": []}
        return {"verdict": "partial", "evidence": result.get("evidence", []), "follow_up": ["Complete the documented work and submit findings."]}

class EngineUnavailable(RuntimeError):
    code = "AI_ENGINE_UNAVAILABLE"

def engine_factory(settings):
    if settings.ai_engine_enabled:
        try:
            from src import MaintenanceEngine
            return MaintenanceEngine()
        except Exception as exc:
            raise EngineUnavailable("AI engine enabled tetapi gagal di-load atau dikonfigurasi") from exc
    if settings.app_env in {"demo", "local", "test"}:
        return StubEngine()
    raise EngineUnavailable("AI engine disabled; offline stub hanya tersedia pada demo mode")

def engine_request(asset, readings, history, business, condition, tier, images=None):
    images = images or []
    try:
        from src import AnalysisRequest, Asset, BusinessContext, MaintenanceRecord, SensorReading, Tier
        return AnalysisRequest(factory_id=asset.factory_id, tier=Tier(tier), asset=Asset(id=asset.id, name=asset.name, type=asset.asset_type, criticality=asset.criticality, specs=asset.specs_json), readings=[SensorReading(tag=x.tag, value=x.value, unit=x.unit, recorded_at=x.recorded_at) for x in readings], images=images, manual_condition=condition, history=[MaintenanceRecord(asset_id=x.asset_id, performed_at=x.performed_at, action=x.action, findings=x.findings, parts_used=x.parts_used_json) for x in history], business=BusinessContext(**business))
    except (ImportError, ModuleNotFoundError):
        class TierValue: value = tier
        return type("Request", (), {"tier": TierValue(), "asset": asset, "readings": readings, "images": images, "history": history, "business": business, "manual_condition": condition})()


def input_disclosure(snapshot):
    """Summarize exactly what the immutable analysis snapshot contained."""
    available = []
    missing = []
    limitations = []

    def mark(token, present, reason):
        (available if present else missing).append(token)
        if reason:
            limitations.append({"token": token, "reason": reason})

    readings = snapshot.get("readings") or []
    mark("readings", bool(readings), "no_readings" if not readings else None)
    history = snapshot.get("history") or []
    mark("history", bool(history), "not_in_snapshot" if not history else None)
    business = snapshot.get("business") or {}
    business_present = any(value not in (None, "", []) for value in business.values())
    mark("business_context", business_present, "not_in_snapshot" if not business_present else None)
    condition = snapshot.get("condition")
    mark("manual_condition", bool(condition), "no_manual_condition" if not condition else None)
    images = snapshot.get("images") or []
    mark("qc_images", bool(images), "no_qc_images" if not images else None)
    return {"available": available, "missing": missing, "limitations": limitations}

def persist_reading(db, asset, data):
    if data.external_id is not None:
        existing = db.scalar(select(models.Reading).where(models.Reading.factory_id == asset.factory_id, models.Reading.asset_id == asset.id, models.Reading.external_id == data.external_id))
        if existing:
            return existing
    reading = models.Reading(factory_id=asset.factory_id, asset_id=asset.id, tag=data.tag, value=data.value, unit=data.unit, recorded_at=data.recorded_at, source=data.source, external_id=data.external_id)
    db.add(reading)
    db.flush()
    return reading

def run_analysis(db, asset, payload, identity, request_id, settings):
    readings = list(db.scalars(__import__('sqlalchemy').select(models.Reading).where(models.Reading.asset_id == asset.id).order_by(models.Reading.recorded_at.desc()).limit(200)))
    history = list(db.scalars(__import__('sqlalchemy').select(models.MaintenanceRecord).where(models.MaintenanceRecord.asset_id == asset.id).order_by(models.MaintenanceRecord.performed_at.desc()).limit(20)))
    context = db.get(models.BusinessContext, asset.id)
    include_business = payload.include_business_context
    include_history = payload.include_history
    business = {"production_schedule": context.production_schedule if include_business and context else None, "spareparts": context.spareparts_json if include_business and context else [], "sparepart_eta": context.sparepart_eta if include_business and context else None, "technicians_available": context.technicians_available if include_business and context else None, "operator_report": context.operator_report if include_business and context else None}
    qc_images = []
    if payload.qc_batch_id:
        batch = db.scalar(select(models.QCBatch).where(models.QCBatch.id == payload.qc_batch_id, models.QCBatch.factory_id == identity.factory_id, models.QCBatch.asset_id == asset.id))
        if not batch:
            raise ValueError("qc_batch_not_found")
        qc_images = list(db.scalars(select(models.QCImage).where(models.QCImage.batch_id == batch.id, models.QCImage.factory_id == identity.factory_id)))
    root = settings.storage_path.resolve()
    image_paths = []
    for image in qc_images:
        path = (root / image.storage_key).resolve()
        if root not in path.parents:
            raise ValueError("invalid_storage_key")
        image_paths.append(str(path))
    effective_condition = payload.manual_condition or (business["operator_report"] if include_business else None)
    request = engine_request(asset, readings, history if include_history else [], business, effective_condition, payload.tier, image_paths)
    started = datetime.now(timezone.utc)
    snapshot = {"asset": {"id": asset.id, "name": asset.name, "type": asset.asset_type, "criticality": asset.criticality, "location": asset.location, "specs": asset.specs_json}, "readings": [{"id": x.id, "tag": x.tag, "value": x.value, "unit": x.unit, "recorded_at": x.recorded_at.isoformat(), "source": x.source, "external_id": x.external_id} for x in readings], "history": [{"id": x.id, "performed_at": x.performed_at.isoformat(), "action": x.action, "findings": x.findings, "parts_used": x.parts_used_json} for x in (history if include_history else [])], "condition": effective_condition, "business": business if include_business else {"production_schedule": None, "spareparts": [], "sparepart_eta": None, "technicians_available": None, "operator_report": None}, "tier": payload.tier, "trigger": payload.trigger, "qc_batch_id": payload.qc_batch_id, "images": image_paths, "engine_mode": "stub"}
    run = models.AnalysisRun(factory_id=identity.factory_id, asset_id=asset.id, tier=payload.tier, trigger=payload.trigger, status="running", started_at=started, request_snapshot_json=snapshot)
    db.add(run); db.flush()
    try:
        engine = engine_factory(settings)
        result = engine.analyze(request)
        if hasattr(result, "model_dump"): result = result.model_dump(mode="json")
        run.status = "succeeded"; run.result_json = result; run.health_score = result.get("health_score"); run.priority = result.get("priority"); run.model = result.get("model"); run.engine_mode = getattr(engine, "mode", "ai_engine"); run.finished_at = datetime.now(timezone.utc)
        audit(db, identity, request_id, "analysis.completed", "analysis", run.id, after={"status": run.status, "priority": run.priority})
    except EngineUnavailable as exc:
        run.status = "failed"; run.error_code = exc.code; run.error_message = str(exc); run.engine_mode = "unavailable"; run.finished_at = datetime.now(timezone.utc)
        audit(db, identity, request_id, "analysis.failed", "analysis", run.id, after={"status": run.status, "error_code": run.error_code})
    except Exception:
        run.status = "failed"; run.error_code = "ANALYSIS_FAILED"; run.error_message = "analysis engine gagal memproses request"; run.engine_mode = "error"; run.finished_at = datetime.now(timezone.utc)
        audit(db, identity, request_id, "analysis.failed", "analysis", run.id, after={"status": run.status, "error_code": run.error_code})
    run.duration_ms = max(0, int((run.finished_at - started).total_seconds() * 1000))
    db.commit(); db.refresh(run)
    return run

TRANSITIONS = {"draft": {"pending_approval", "cancelled"}, "pending_approval": {"approved", "rejected", "cancelled"}, "approved": {"scheduled", "cancelled"}, "scheduled": {"in_progress", "cancelled"}, "in_progress": {"blocked", "cancelled"}, "blocked": {"in_progress", "cancelled"}, "completed": set(), "cancelled": set(), "rejected": set()}
def transition(db, order, target, identity, request_id, reason: str | None = None):
    """The one state machine. `main.py` used to carry a second, divergent copy."""
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
    db.commit(); db.refresh(order); return order


def submit_technician_result(db, order, payload, identity, request_id):
    result = payload.model_dump(mode="json")
    if order.technician_result_json is not None:
        if order.technician_result_json != result:
            raise ValueError("conflicting_technician_result")
        return order
    if order.status != "in_progress":
        raise ValueError(f"invalid_transition:{order.status}->result")
    order.technician_result_json = result
    order.result_submitted_at = datetime.now(timezone.utc)
    audit(db, identity, request_id, "work_order.result_submitted", "work_order", order.id, after={"status": order.status, "result": result})
    db.commit(); db.refresh(order)
    return order


def verify_work_order(db, order, identity, request_id, settings):
    if order.verification_json is not None:
        if order.status == "completed" and (order.verification_json.get("ingestion") or {}).get("status") != "ready":
            document = db.scalar(select(models.Document).where(
                models.Document.factory_id == order.factory_id,
                models.Document.storage_key == f"generated/{order.factory_id}/{order.id}.txt",
            ))
            if document:
                _finish_history_ingestion(db, document, order, settings)
        return order
    if order.status != "in_progress":
        raise ValueError(f"invalid_transition:{order.status}->verification")
    if order.technician_result_json is None:
        raise ValueError("technician_result_required")
    try:
        from src import TechnicianResult, VerificationResult, WorkOrder
        technician_result = TechnicianResult(**order.technician_result_json)
        work_order = WorkOrder(
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
        verification = engine_factory(settings).verify(work_order, technician_result)
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
        audit(db, identity, request_id, "work_order.status_changed", "work_order", order.id, before={"status": before}, after={"status": "completed", "verdict": "resolved"})
        record = models.MaintenanceRecord(
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
        document = models.Document(
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
    # Commit the app database before allowing pgvector's independent commit.
    db.commit(); db.refresh(order)
    if verification.get("verdict") == "resolved":
        document = db.scalar(select(models.Document).where(
            models.Document.factory_id == order.factory_id,
            models.Document.storage_key == f"generated/{order.factory_id}/{order.id}.txt",
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
    # This status update is intentionally a separate transaction from the
    # authoritative work-order/history commit above.
    db.commit()
