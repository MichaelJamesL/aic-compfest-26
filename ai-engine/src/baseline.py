"""Per-machine sensor baselines: median and MAD per tag, learned from history.

The difference from the IQR fence in `signals` is what "anomalous" means. The
fence asks whether a point is extreme *within the batch being scored*, so a
whole batch sitting somewhere it should not looks normal to itself. A baseline
asks whether a point is unusual *for this machine*, which is the question
maintenance actually cares about.

No baseline on disk means no opinion — `score` returns None and the caller
falls back to the fence, so machines registered without history keep working.
Tags the baseline never saw fall back the same way, per tag.

Why a robust z-score and not a forest: see docs/adr/0001-sensor-anomaly-baseline.md.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from . import config
from .schemas import Anomaly, SensorReading

MIN_POINTS = config.MIN_POINTS_PER_TAG

# Modified z-score cutoff. 3.5 is the Iglewicz-Hoaglin convention.
Z_FLAG = 3.5
# Scales MAD to be a consistent estimator of sigma for normal data.
MAD_TO_SIGMA = 1.4826


def _path(asset_id: str) -> Path:
    # Named by asset id, which is a uuid — no path traversal from a
    # caller-supplied name, and no collisions between factories.
    return Path(config.BASELINE_DIR) / f"{asset_id}.json"


def _by_tag(readings: list[SensorReading]) -> dict[str, list[SensorReading]]:
    grouped: dict[str, list[SensorReading]] = defaultdict(list)
    for reading in readings:
        grouped[reading.tag].append(reading)
    return grouped


def _scale(values: np.ndarray, median: float) -> float:
    """Robust spread, with a floor so a rock-steady sensor is not infinitely touchy."""
    mad = float(np.median(np.abs(values - median))) * MAD_TO_SIGMA
    # ponytail: floor at 1% of the median, so a sensor that reads exactly 50.0
    # forever does not call 50.1 a critical anomaly. Tune per tag if a genuinely
    # tight process needs finer resolution than 1%.
    return max(mad, abs(median) * 0.01, 1e-6)


def fit(asset_id: str, readings: list[SensorReading]) -> dict[str, int]:
    """Fit one baseline per tag with enough history. Returns {tag: points used}.

    Tags below MIN_POINTS are skipped rather than fitted badly — a baseline
    built on four points is worse than the fence it would replace.
    """
    fitted: dict[str, dict] = {}
    for tag, series in _by_tag(readings).items():
        values = np.array([r.value for r in series], dtype=float)
        if values.size < MIN_POINTS:
            continue
        median = float(np.median(values))
        fitted[tag] = {"median": median, "scale": _scale(values, median), "points": int(values.size)}

    if not fitted:
        return {}
    path = _path(asset_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fitted, indent=2))
    return {tag: stats["points"] for tag, stats in fitted.items()}


def load(asset_id: str) -> dict[str, dict] | None:
    path = _path(asset_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text()) or None
    except (ValueError, OSError):
        # A corrupt or stale-format baseline must not take an analysis down.
        return None


def score(asset_id: str, readings: list[SensorReading]) -> tuple[list[Anomaly], set[str]] | None:
    """(anomalies, tags this baseline covers), or None when there is no baseline.

    The covered set is what lets the caller fence the remaining tags instead of
    silently ignoring a sensor the machine did not have at registration.
    """
    trained = load(asset_id)
    if trained is None:
        return None

    from .signals import _severity

    anomalies: list[Anomaly] = []
    for tag, series in _by_tag(readings).items():
        stats = trained.get(tag)
        if not stats:
            continue
        values = np.array([r.value for r in series], dtype=float)
        if not values.size:
            continue
        median, scale = stats["median"], stats["scale"]
        z = np.abs(values - median) / scale
        worst = int(np.argmax(z))
        if z[worst] <= Z_FLAG:
            continue
        band = Z_FLAG * scale
        anomalies.append(
            Anomaly(
                tag=tag,
                observed=round(float(values[worst]), 2),
                expected_range=(round(median - band, 2), round(median + band, 2)),
                # How many flag-widths past the band it sits, so the existing
                # severity ladder keeps its meaning.
                severity=_severity(float(z[worst]) / Z_FLAG - 1.0),
                method="robust_z",
            )
        )
    return anomalies, set(trained)


def demo() -> None:
    """Runnable check: a baseline sees what the batch-local fence cannot."""
    import tempfile
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)

    def series(tag: str, values: list[float]) -> list[SensorReading]:
        return [
            SensorReading(tag=tag, value=v, unit="c", recorded_at=now + timedelta(hours=i))
            for i, v in enumerate(values)
        ]

    original = config.BASELINE_DIR
    with tempfile.TemporaryDirectory() as tmp:
        config.BASELINE_DIR = tmp
        try:
            from .signals import detect_anomalies

            assert score("never-fitted", series("t", [1.0])) is None, "no baseline, no opinion"

            history = series("bearing_temp_c", [50.0 + (i % 3) for i in range(60)])
            assert fit("pump-1", history) == {"bearing_temp_c": 60}
            # Too little history to fit at all — the fence stays in charge.
            assert fit("pump-2", series("bearing_temp_c", [50.0, 51.0])) == {}
            assert score("pump-2", history) is None

            # Every point sits at 80. Flat, so the fence inside this batch finds
            # nothing, while the baseline knows 80 is not normal for this machine.
            hot = series("bearing_temp_c", [80.0] * 12)
            assert detect_anomalies(hot) == []
            found = detect_anomalies(hot, "pump-1")
            assert [a.method for a in found] == ["robust_z"], found
            assert found[0].observed == 80.0 and found[0].severity == "critical"

            # Readings that look like the history are not anomalies.
            assert detect_anomalies(series("bearing_temp_c", [50.0, 51.0, 52.0]), "pump-1") == []
            # An edge-of-normal value is normal — the case a forest could not tell
            # apart from 80 (see the ADR).
            assert detect_anomalies(series("bearing_temp_c", [52.0] * 12), "pump-1") == []

            # A tag the baseline never saw still gets the fence, not silence.
            unknown = series("vibration_mm_s", [1.0] * 11 + [99.0])
            assert [a.method for a in detect_anomalies(unknown, "pump-1")] == ["iqr"]
        finally:
            config.BASELINE_DIR = original

    print("baseline demo ok")


if __name__ == "__main__":
    demo()
