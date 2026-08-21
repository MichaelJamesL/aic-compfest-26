"""Deterministic anomaly detection and health scoring. No LLM — the numbers
are reproducible and defensible, and the LLM explains them rather than
inventing them.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np

from . import config
from .schemas import Anomaly, Asset, DefectFinding, MaintenanceRecord, SensorReading

# Whether a tag has enough points to be scored at all.
MIN_POINTS = config.MIN_POINTS_PER_TAG

# IQR multiplier for the inner fence (robust outlier boundary).
IQR_K = 1.5

# How many fences out a point is, mapped to severity.
_SEVERITY_BY_MULT = [
    (2.0, "critical"),
    (1.5, "high"),
    (1.0, "medium"),
    (0.0, "low"),
]

# Deductions from 100, keyed by severity. Tunable without touching logic.
HEALTH_WEIGHTS = {
    "anomaly": {"low": 5, "medium": 10, "high": 20, "critical": 30},
    "defect": {"low": 5, "medium": 10, "high": 20, "critical": 30},
    "overdue": 10,       # days since last maintenance (per interval, capped)
    "repeat": 5,         # per repeat failure in the window
}

# Default maintenance interval in days; can be overridden by asset spec.
DEFAULT_MAINT_INTERVAL_DAYS = 90
# Window (days) over which repeat failures on the same tag are counted.
REPEAT_WINDOW_DAYS = 30


def _group_by_tag(readings: list[SensorReading]) -> dict[str, list[SensorReading]]:
    grouped: dict[str, list[SensorReading]] = defaultdict(list)
    for r in readings:
        grouped[r.tag].append(r)
    return grouped


def _fence(values: np.ndarray) -> tuple[float, float]:
    lo, hi = np.percentile(values, [25, 75])
    iqr = hi - lo
    return lo - IQR_K * iqr, hi + IQR_K * iqr


def detect_anomalies(readings: list[SensorReading]) -> list[Anomaly]:
    """Per-tag rolling-absent IQR fence. Flag the most extreme point per tag
    that falls outside the fence. Returns [] when a tag has < MIN_POINTS.
    """
    anomalies: list[Anomaly] = []
    for tag, series in _group_by_tag(readings).items():
        if len(series) < MIN_POINTS:
            continue
        values = np.array([r.value for r in series], dtype=float)
        lower, upper = _fence(values)
        # The point furthest beyond the fence (outliers only).
        below = values[values < lower]
        above = values[values > upper]
        if not below.size and not above.size:
            continue
        observed, upper_out, lower_out = np.max(above), 0.0, 0.0
        if above.size:
            observed, upper_out = np.max(above), np.max(above)
        if below.size:
            lower_val = np.min(below)
            if lower_out == 0.0 or abs(lower_val - lower) > abs(observed - upper):
                observed = lower_val
        # How many (half-)IQRs beyond the fence the observation sits.
        margin = max(abs(observed - upper), abs(lower - observed))
        width = iqr_dist = upper - lower
        mult = margin / (width / 2) if width else 0.0
        severity = _severity(mult)
        expected = (round(float(lower), 2), round(float(upper), 2))
        anomalies.append(
            Anomaly(
                tag=tag,
                observed=round(float(observed), 2),
                expected_range=expected,
                severity=severity,
                method="iqr",
            )
        )
    return anomalies


def _severity(mult: float) -> str:
    for threshold, sev in _SEVERITY_BY_MULT:
        if mult > threshold:
            return sev
    return "low"


def _days_since(dt: datetime, now: datetime) -> float:
    return max(0.0, (now - dt).total_seconds() / 86400.0)


def health_score(
    asset: Asset,
    anomalies: list[Anomaly],
    history: list[MaintenanceRecord],
    defects: list[DefectFinding] | None = None,
    now: datetime | None = None,
) -> tuple[int, str]:
    """Weighted deduction from 100. Returns (score, summary).

    Deductions: anomaly severity, defect severity, overdue maintenance vs
    the asset's interval, and repeat failures on the same tag within
    REPEAT_WINDOW_DAYS.
    """
    now = now or datetime.now(timezone.utc)
    score = 100.0
    reasons: list[str] = []

    for a in anomalies:
        score -= HEALTH_WEIGHTS["anomaly"][a.severity]
        reasons.append(f"{a.tag} anomaly ({a.severity})")

    for d in (defects or []):
        if d.label == "defect":
            score -= HEALTH_WEIGHTS["defect"][d.severity]
            reasons.append(f"{d.image} defect ({d.severity})")

    interval = DEFAULT_MAINT_INTERVAL_DAYS
    if asset.specs.get("maintenance_interval_days"):
        interval = int(asset.specs["maintenance_interval_days"])

    if history:
        last = max(history, key=lambda r: r.performed_at).performed_at
        overdue = _days_since(last, now)
        if overdue > interval:
            score -= HEALTH_WEIGHTS["overdue"]
            reasons.append(f"maintenance overdue by {overdue - interval:.0f}d")

    # Repeat failures: same tag failed more than once in the window.
    recent_cutoff = now - timedelta(days=REPEAT_WINDOW_DAYS)
    tag_failures: dict[str, int] = defaultdict(int)
    for r in history:
        if r.performed_at >= recent_cutoff and r.asset_id == asset.id:
            tag_failures[r.findings or r.action] += 1
    for _, count in tag_failures.items():
        if count > 1:
            score -= HEALTH_WEIGHTS["repeat"] * (count - 1)
            reasons.append(f"repeat failure x{count}")

    score = int(max(0, min(100, round(score))))

    if score >= 80:
        summary = "Asset operating within normal parameters."
    elif score >= 60:
        summary = "Minor concerns; schedule inspection."
    elif score >= 40:
        summary = "Significant degradation; plan maintenance soon."
    else:
        summary = "Critical condition; intervene immediately."
    if reasons:
        summary += " " + "; ".join(reasons) + "."
    return score, summary