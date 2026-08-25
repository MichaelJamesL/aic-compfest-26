from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import floor
from types import SimpleNamespace

from sqlalchemy import select

from ..analysis.models import AnalysisRun
from ..assets.models import BusinessContext
from ..assets.service import read_inventory
from ..config import get_settings
from ..maintenance.models import MaintenanceRecord
from ..qc.models import QCBatch, QCImage
from ..readings.models import Reading
from ..readings.service import persist_reading
from ..repositories import audit

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
    mode = "offline_stub"

    def analyze(self, request):
        try:
            from src.signals import detect_anomalies, health_score
        except ImportError:
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
        return {
            "health_score": score,
            "health_summary": summary,
            "anomalies": [a.model_dump(mode="json") for a in anomalies],
            "defects": [],
            "root_causes": [{"cause": "Condition requires inspection" if condition else "No significant signal", "confidence": 0.55, "evidence": [condition] if condition else []}],
            "recommendation": "Inspect and schedule preventive maintenance" if priority != "low" else "Continue monitoring",
            "priority": priority,
            "recommended_window": "Next available maintenance window",
            "explanation": "Generated by offline Starter engine stub",
            "blockers": [],
            "work_order": {"title": "Inspect asset", "steps": ["Inspect machine condition", "Verify readings"], "parts": [], "est_duration_h": 2, "required_skills": ["maintenance"], "safety_notes": ["Apply lockout/tagout"]},
            "tier": request.tier.value,
            "model": "offline-stub",
            "sources": [],
        }

    def ask(self, request, question):
        return f"Offline Starter answer for '{question}': review the asset condition and applicable SOP."

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
            raise EngineUnavailable("AI engine enabled but failed to load or configure") from exc
    if settings.app_env in {"demo", "local", "test"}:
        return StubEngine()
    raise EngineUnavailable("AI engine disabled; offline stub only available in demo mode")


def engine_request(asset, readings, history, business, condition, tier, images=None, qc_batches=None):
    images = images or []
    qc_batches = qc_batches or []
    try:
        from src import AnalysisRequest, Asset as EngineAsset, BusinessContext as EngineBusinessContext, MaintenanceRecord as EngineMaintenanceRecord, QCBatch as EngineQCBatch, SensorReading, Tier
        return AnalysisRequest(
            tier=Tier(tier),
            # Without this, knowledge.search filters on factory_id = NULL and
            # every retrieval comes back empty — silently, since the field is optional.
            factory_id=asset.factory_id,
            asset=EngineAsset(id=asset.id, name=asset.name, type=asset.asset_type,
                              criticality=asset.criticality, specs=asset.specs_json),
            readings=[SensorReading(tag=x.tag, value=x.value, unit=x.unit,
                                    recorded_at=x.recorded_at) for x in readings],
            images=images,
            qc_batches=[EngineQCBatch(**b) for b in qc_batches],
            manual_condition=condition,
            history=[EngineMaintenanceRecord(asset_id=x.asset_id, performed_at=x.performed_at,
                                             action=x.action, findings=x.findings,
                                             parts_used=x.parts_used_json) for x in history],
            business=EngineBusinessContext(**{k: v for k, v in business.items() if v is not None}),
        )
    except (ImportError, ModuleNotFoundError):
        class TierValue:
            value = tier
        return type("Request", (), {
            "tier": TierValue(),
            "asset": asset,
            "readings": readings,
            "images": images,
            "qc_batches": qc_batches,
            "history": history,
            "business": business,
            "manual_condition": condition,
        })()


def input_disclosure(snapshot):
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
    business_present = any(business.values())
    mark("business_context", business_present, "not_in_snapshot" if not business_present else None)
    condition = snapshot.get("condition")
    mark("manual_condition", bool(condition), "no_manual_condition" if not condition else None)
    images = snapshot.get("images") or []
    mark("qc_images", bool(images), "no_qc_images" if not images else None)
    return {"available": available, "missing": missing, "limitations": limitations}


def _inventory_for_asset(db, asset, include_business=True):
    """Only the parts that fit this machine — the warehouse at large is noise to the engine."""
    if not include_business:
        return []
    return [
        {key: value for key, value in part.items() if key != "asset_ids"}
        for part in read_inventory(db, asset.factory_id, asset_id=asset.id)
    ]


def run_analysis(db, asset, payload, identity, request_id, settings):
    readings = list(db.scalars(select(Reading).where(Reading.asset_id == asset.id).order_by(Reading.recorded_at.desc()).limit(200)))
    history = list(db.scalars(select(MaintenanceRecord).where(MaintenanceRecord.asset_id == asset.id).order_by(MaintenanceRecord.performed_at.desc()).limit(20)))
    context = db.get(BusinessContext, identity.factory_id)
    include_business = payload.include_business_context
    include_history = payload.include_history
    business = {
        "production_schedule": context.production_schedule if include_business and context else None,
        "inventory": _inventory_for_asset(db, asset, include_business),
        "technicians": context.technicians_json if include_business and context else [],
        # per-machine, unlike the rest: it rides along so the engine sees it in one place
        "operator_report": asset.operator_report if include_business else None,
    }
    qc_images = []
    batch = None
    if payload.qc_batch_id:
        batch = db.scalar(select(QCBatch).where(QCBatch.id == payload.qc_batch_id, QCBatch.factory_id == identity.factory_id, QCBatch.asset_id == asset.id))
        if not batch:
            raise ValueError("qc_batch_not_found")
        qc_images = list(db.scalars(select(QCImage).where(QCImage.batch_id == batch.id, QCImage.factory_id == identity.factory_id)))
    root = settings.storage_path.resolve()
    image_paths = []
    for image in qc_images:
        path = (root / image.storage_key).resolve()
        if root not in path.parents:
            raise ValueError("invalid_storage_key")
        image_paths.append(str(path))
    qc_batches = []
    if batch and image_paths:
        qc_batches.append({
            "phase": batch.phase or "inspection",
            "asset_id": asset.id,
            "product": batch.product or asset.asset_type,
            "images": image_paths,
        })
    effective_condition = payload.manual_condition or (business["operator_report"] if include_business else None)
    request = engine_request(asset, readings, history if include_history else [], business, effective_condition, payload.tier, image_paths, qc_batches)
    started = datetime.now(timezone.utc)
    snapshot = {
        "asset": {"id": asset.id, "name": asset.name, "type": asset.asset_type, "criticality": asset.criticality, "location": asset.location, "specs": asset.specs_json},
        "readings": [{"id": x.id, "tag": x.tag, "value": x.value, "unit": x.unit, "recorded_at": x.recorded_at.isoformat(), "source": x.source, "external_id": x.external_id} for x in readings],
        "history": [{"id": x.id, "performed_at": x.performed_at.isoformat(), "action": x.action, "findings": x.findings, "parts_used": x.parts_used_json} for x in (history if include_history else [])],
        "condition": effective_condition,
        "business": business,
        "tier": payload.tier,
        "trigger": payload.trigger,
        "qc_batch_id": payload.qc_batch_id,
        "images": image_paths,
        "engine_mode": "stub",
    }
    run = AnalysisRun(factory_id=identity.factory_id, asset_id=asset.id, tier=payload.tier, trigger=payload.trigger, status="running", started_at=started, request_snapshot_json=snapshot)
    db.add(run)
    db.flush()
    try:
        engine = engine_factory(settings)
        result = engine.analyze(request)
        if hasattr(result, "model_dump"):
            result = result.model_dump(mode="json")
        run.status = "succeeded"
        run.result_json = result
        run.health_score = result.get("health_score")
        run.priority = result.get("priority")
        run.model = result.get("model")
        run.engine_mode = getattr(engine, "mode", "ai_engine")
        run.finished_at = datetime.now(timezone.utc)
        audit(db, identity, request_id, "analysis.completed", "analysis", run.id, after={"status": run.status, "priority": run.priority})
    except EngineUnavailable as exc:
        run.status = "failed"
        run.error_code = exc.code
        run.error_message = str(exc)
        run.engine_mode = "unavailable"
        run.finished_at = datetime.now(timezone.utc)
        audit(db, identity, request_id, "analysis.failed", "analysis", run.id, after={"status": run.status, "error_code": run.error_code})
    except Exception:
        run.status = "failed"
        run.error_code = "ANALYSIS_FAILED"
        run.error_message = "analysis engine failed to process request"
        run.engine_mode = "error"
        run.finished_at = datetime.now(timezone.utc)
        audit(db, identity, request_id, "analysis.failed", "analysis", run.id, after={"status": run.status, "error_code": run.error_code})
    run.duration_ms = max(0, int((run.finished_at - started).total_seconds() * 1000))
    db.commit()
    db.refresh(run)
    return run