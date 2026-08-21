"""Score the MaintenanceEngine against the labelled cases in cases.yaml.

Usage:
    python run_eval.py

Requires DEEPSEEK_API_KEY (the engine calls the real DeepSeek API). Metrics:
priority accuracy (exact match), root-cause hit rate (any expected keyword in
recommendation or root_causes), and retry rate. Retries are owned by
pydantic_ai (validation re-prompts); each retry is an extra model request, so
retries = usage.requests - 1.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from src.config import DEEPSEEK_API_KEY  # noqa: E402
from src.engine import MaintenanceEngine  # noqa: E402
from src.schemas import (  # noqa: E402
    AnalysisRequest,
    AnalysisResult,
    Asset,
    BusinessContext,
    MaintenanceRecord,
    SensorReading,
    Tier,
)


def _parse_dt(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _build_request(case: dict) -> AnalysisRequest:
    return AnalysisRequest(
        tier=Tier(case["tier"]),
        asset=Asset(**case["asset"]),
        readings=[
            SensorReading(tag=r["tag"], value=r["value"], unit=r["unit"], recorded_at=_parse_dt(r["recorded_at"]))
            for r in case.get("readings", [])
        ],
        manual_condition=case.get("manual_condition"),
        history=[
            MaintenanceRecord(
                asset_id=h["asset_id"],
                performed_at=_parse_dt(h["performed_at"]),
                action=h.get("action", ""),
                findings=h.get("findings", ""),
                parts_used=h.get("parts_used", []),
            )
            for h in case.get("history", [])
        ],
        business=BusinessContext(**case.get("business", {})),
        images=case.get("images", []),
    )


def _priority_accuracy(result: AnalysisResult, expected: dict) -> bool:
    return result.priority == expected["priority"]


def _root_cause_hit(result: AnalysisResult, expected: dict) -> bool:
    haystack = " ".join(
        [result.recommendation, *[rc.cause for rc in result.root_causes]]
    ).lower()
    return any(k.lower() in haystack for k in expected.get("root_cause", []))


def _references_window(result: AnalysisResult, expected: dict) -> bool:
    want = bool(expected.get("references_window", False))
    has = bool(result.recommended_window)
    return (not want) or has


def _blocker_hit(result: AnalysisResult, expected: dict) -> bool:
    want = [b.lower() for b in expected.get("blockers", [])]
    if not want:
        return True
    haystack = " ".join(result.blockers).lower()
    return any(b in haystack for b in want)


def _metrics(result: AnalysisResult, expected: dict) -> dict[str, bool]:
    return {
        "priority": _priority_accuracy(result, expected),
        "root_cause": _root_cause_hit(result, expected),
        "window": _references_window(result, expected),
        "blockers": _blocker_hit(result, expected),
    }


def _retry_count(engine: MaintenanceEngine) -> int:
    """pydantic_ai retries map to extra model requests: requests - 1."""
    usage = engine.last_usage
    return (usage.requests - 1) if usage else 0


def main() -> int:
    if not DEEPSEEK_API_KEY:
        print("ERROR: DEEPSEEK_API_KEY is not set. Set it to run the eval.", file=sys.stderr)
        return 1

    cases_path = HERE / "cases.yaml"
    cases = yaml.safe_load(cases_path.read_text())
    engine = MaintenanceEngine()

    rows: list[dict] = []
    for case in cases:
        row = {"id": case["id"], "error": None}
        try:
            request = _build_request(case)
            result = engine.analyze(request)
            row.update(_metrics(result, case["expected"]))
            row["retries"] = _retry_count(engine)
        except Exception as exc:  # one failure must not kill the run
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)

    total = len(rows)
    print(f"{'case':<28} {'priority':<9} {'root':<6} {'window':<7} {'blockers':<8} {'retries':<8} note")
    print("-" * 78)
    for r in rows:
        if r["error"]:
            print(f"{r['id']:<28} {'-':<9} {'-':<6} {'-':<7} {'-':<8} {'-':<8} FAIL: {r['error']}")
            continue
        print(
            f"{r['id']:<28} {str(r['priority']):<9} {str(r['root_cause']):<6} "
            f"{str(r['window']):<7} {str(r['blockers']):<8} {str(r.get('retries', 0)):<8}"
        )

    ok = [r for r in rows if not r["error"]]
    if not ok:
        print("\nAll cases failed.")
        return 1

    def avg(key: str) -> float:
        return sum(1 for r in ok if r.get(key)) / len(ok)

    print("\nOverall (excludes failed cases):")
    print(f"  priority accuracy      : {avg('priority'):.0%}")
    print(f"  root-cause hit rate    : {avg('root_cause'):.0%}")
    print(f"  window-match rate      : {avg('window'):.0%}")
    print(f"  blocker-match rate     : {avg('blockers'):.0%}")
    print(f"  total retries          : {sum(r.get('retries', 0) for r in ok)}")
    print(f"  failed cases           : {total - len(ok)}/{total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())