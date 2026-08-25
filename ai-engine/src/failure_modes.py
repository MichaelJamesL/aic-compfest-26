"""Defect class -> candidate failure modes — NOT USED BY THE CURRENT PIPELINE.

Kept for future development, together with `classify`. Every link here starts
from a defect *class*, and the current pipeline is PatchCore-only: it reports
that an image is abnormal, not which defect it is, so there is no key to look
up. Re-wiring `classify` re-enables this module, and the engine must then apply
`priority_delta` after the model answers — the escalation belongs on the
deterministic side, not in the model's judgement.

Original docstring follows.

Defect class -> candidate machine failure modes, corroborated by sensors.

`mapping/qc_failure_modes.yaml` is engineering knowledge, not something the
system learned, and the rule it states is the point of this module:

    a defect class proposes failure modes; priority moves only when a sensor
    signal corroborates one. No corroboration, no escalation — and say so.

So a link is always reported, with `corroborated_by` empty when nothing backed
it up, and `priority_delta` zeroed in that case. Silence would let a scratch
that is usually a handling problem quietly raise a machine's priority.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml

from . import config
from .schemas import FailureModeLink, SensorReading

_TABLE: dict | None = None
# Recent-vs-earlier split for trend and variance rules.
WINDOW = 0.5


def _load() -> dict:
    global _TABLE
    if _TABLE is None:
        path = Path(config.FAILURE_MODE_TABLE)
        _TABLE = yaml.safe_load(path.read_text()) if path.is_file() else {"defects": []}
    return _TABLE


def _series(readings: list[SensorReading], tag: str) -> np.ndarray:
    ordered = sorted((r for r in readings if r.tag == tag), key=lambda r: r.recorded_at)
    return np.array([r.value for r in ordered], dtype=float)


def _holds(rule: str, values: np.ndarray) -> bool:
    """Evaluate one corroboration rule against a tag's series.

    The table writes rules as engineering prose ("> p90 baseline", "trend_up
    over last 50 cycles", "variance > 2x baseline"). Only the three kinds that
    actually appear are understood; anything else is treated as not
    corroborated rather than quietly assumed true.
    """
    if values.size < 4:
        return False
    rule = rule.lower()
    half = max(2, int(values.size * WINDOW))
    recent, earlier = values[-half:], values[:-half]

    if "p90" in rule:
        return bool(values[-1] > np.percentile(values, 90))
    if "trend_up" in rule:
        slope = np.polyfit(np.arange(values.size), values, 1)[0]
        return bool(slope > 0)
    if "variance" in rule:
        if earlier.size < 2:
            return False
        baseline = float(np.var(earlier))
        return bool(np.var(recent) > 2 * baseline) if baseline > 0 else False
    return False


def links(defect_classes: list[str], readings: list[SensorReading]) -> list[FailureModeLink]:
    """One link per distinct non-nominal defect class seen, in table order."""
    rows = {row["defect_class"]: row for row in (_load().get("defects") or [])}
    seen: dict[str, int] = defaultdict(int)
    for name in defect_classes:
        seen[name] += 1

    out: list[FailureModeLink] = []
    for name, count in seen.items():
        row = rows.get(name)
        if not row or not row.get("candidate_failure_modes"):
            continue
        corroborated = [
            check["tag"]
            for check in (row.get("corroborate") or [])
            if _holds(str(check.get("rule", "")), _series(readings, check["tag"]))
        ]
        out.append(
            FailureModeLink(
                defect_class=name,
                images=count,
                failure_modes=list(row["candidate_failure_modes"]),
                corroborated_by=corroborated,
                # The restraint the table asks for: proposed modes stay
                # proposals until a signal backs them.
                priority_delta=int(row.get("priority_delta", 0)) if corroborated else 0,
                recommended_action=row.get("recommended_action", ""),
                source=row.get("source") or row.get("note", ""),
            )
        )
    return sorted(out, key=lambda link: (-link.priority_delta, link.defect_class))


def demo() -> None:
    """Runnable check: no corroboration means no escalation."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)

    def series(tag: str, values: list[float]) -> list[SensorReading]:
        return [
            SensorReading(tag=tag, value=v, unit="", recorded_at=now + timedelta(minutes=i))
            for i, v in enumerate(values)
        ]

    rising = series("torque_nm", [10.0 + i for i in range(20)])
    flat = series("torque_nm", [10.0] * 20)

    backed = links(["thread_side"], rising)
    assert backed and backed[0].corroborated_by == ["torque_nm"], backed
    assert backed[0].priority_delta == 1

    unbacked = links(["thread_side"], flat)
    assert unbacked and unbacked[0].corroborated_by == []
    # The whole point: proposed, not escalated.
    assert unbacked[0].priority_delta == 0
    assert unbacked[0].failure_modes == ["tool_wear", "axis_backlash"]

    # A class the table says is usually not the machine's fault never escalates.
    handling = links(["scratch_head"], rising)
    assert handling and handling[0].priority_delta == 0

    # good is not a defect, and an unknown class is not invented.
    assert links(["good", "not_a_class"], rising) == []
    # Repeats are counted, not duplicated.
    assert links(["thread_side", "thread_side"], flat)[0].images == 2

    print("failure_modes demo ok")


if __name__ == "__main__":
    demo()
