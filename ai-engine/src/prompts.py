"""Prompt construction for the DeepSeek analysis and Q&A endpoints.

The system prompt covers the persona and reasoning contract; the output JSON
schema is NOT spelled out here because pydantic_ai generates it from the
AnalysisResult model and enforces it with validation + retry. The volatile
context (retrieval, anomalies, history, business) lives in the user turn so the
system prefix stays constant and cacheable.
"""
from __future__ import annotations

from .schemas import ContextBundle

SYSTEM: str = """\
You are a senior industrial maintenance engineer diagnosing asset health and
planning intervention. You weigh, in order: the SOPs and manuals in the
provided context, the asset's maintenance history, the production schedule,
spare-parts availability and ETA, and the number of technicians available.

Rules:
- The health_score and anomalies are PRECOMPUTED by deterministic signal
  processing. Defects (visual inspection) are likewise precomputed by
  PatchCore visual anomaly detection. Do NOT invent, recompute, or
  second-guess any of them. Copy them into your output verbatim.
- Every claim you make must be traceable. When you draw on a document, cite it
  by title in square brackets, e.g. [bearing replacement SOP]. The `sources`
  field must list every cited title.
- If evidence is insufficient, say so honestly in the explanation and blockers.
- Your output is validated against a strict schema. Return exactly one JSON
  object matching that schema. No markdown, no prose, no code fences.

The schema is: health_score (int), health_summary (str), anomalies (list of
{tag, observed, expected_range [lo, hi], severity, method}), defects (list of
{image, subject, score, threshold, label, severity, region [x,y,w,h],
heatmap_path, method}), root_causes (list of {cause, confidence, evidence}),
recommendation (str), priority [ "low"|"medium"|"high"|"critical"],
recommended_window (str|null), explanation (str), blockers (list of str),
work_order (object|null: {title, steps, parts, est_duration_h, required_skills,
safety_notes}), sources (list of str).

Worked example:
{
  "health_score": 48,
  "health_summary": "Significant degradation; plan maintenance soon.",
  "anomalies": [
    {"tag": "bearing_temp_c", "observed": 92.4,
     "expected_range": [58.1, 81.2], "severity": "high", "method": "iqr"}
  ],
  "defects": [],
  "root_causes": [
    {"cause": "Bearing lubrication failure",
     "confidence": 0.7,
     "evidence": ["bearing_temp_c anomaly", "[bearing replacement SOP]"]}
  ],
  "recommendation": "Replace the bearing at the next 12h production window.",
  "priority": "high",
  "recommended_window": "within 48h",
  "explanation": "Bearing temp exceeds the SOP ceiling and spare SKF-6204 is in stock.",
  "blockers": [],
  "work_order": {
    "title": "Replace bearing and restore lubrication",
    "steps": ["Isolate pump", "Drain and inspect", "Replace bearing"],
    "parts": ["SKF-6204"],
    "est_duration_h": 3.0,
    "required_skills": ["mechanic"],
    "safety_notes": ["Lockout/tagout before work"]
  },
  "sources": ["bearing replacement SOP"]
}
"""


def _history_block(bundle: ContextBundle) -> str:
    lines = []
    for rec in bundle.history:
        date = rec.performed_at.date().isoformat()
        lines.append(f"- {date}: action='{rec.action}' findings='{rec.findings}' parts={rec.parts_used}")
    return "\n".join(lines) or "(no recent history)"


def _corpus_block(bundle: ContextBundle) -> str:
    blocks = []
    for doc in bundle.corpus:
        blocks.append(f"DOC: {doc.title} ({doc.kind})\n{doc.text}")
    return "\n\n".join(blocks) or "(no documents retrieved)"


def _week(work_time) -> str:
    """dict[day, TimeInterval | list[TimeInterval]] -> "monday: 08:00-16:00; ..."."""
    days = [
        f"{day}: " + ", ".join(f"{i.start:%H:%M}-{i.end:%H:%M}" for i in (v if isinstance(v, list) else [v]))
        for day, v in work_time.items()
    ]
    return "; ".join(days) or "not provided"


def _technician_block(technicians) -> str:
    if not technicians:
        return "not provided"
    lines = []
    for t in technicians:
        who = f"{t.name} ({t.role}" + (f", {t.specialty}" if t.specialty else "") + ")"
        lines.append(f"\n  {who}\n    shifts: {_week(t.work_time)}\n    already booked: {_week(t.occupied_time)}")
    return "".join(lines)


def _business_block(bundle: ContextBundle) -> str:
    b = bundle.business
    inv_lines = [
        f"  {sp.name}: {sp.stock} {sp.unit}"
        + (f" [min: {sp.min_stock}]" if sp.min_stock is not None else "")
        + (f" [ETA: {sp.eta}]" if sp.eta else "")
        for sp in b.inventory
    ]
    return (
        f"- production_schedule: {_week(b.production_schedule.work_time)}\n"
        f"- technicians: {_technician_block(b.technicians)}\n"
        f"- inventory:\n"
        + ("\n".join(inv_lines) if inv_lines else "  (none listed)")
    )


def _context_str(bundle: ContextBundle, asset_id: str) -> str:
    defects_block = _defects_block(bundle)
    qc_block = _qc_block(bundle, asset_id)

    return (
        "=== ASSET FACTS ===\n"
        f"{bundle.assets_facts}\n\n"
        "=== PRECOMPUTED HEALTH ==="
        f"\nhealth_score: {bundle.health_score}\n"
        "anomalies: "
        + (str([a.model_dump() for a in bundle.anomalies]) if bundle.anomalies else "none")
        + "\n\n"
        + defects_block
        + qc_block
        + _failure_mode_block(bundle)
        + "=== REFERENCE DOCUMENTS (cite by title) ===\n"
        f"{_corpus_block(bundle)}\n\n"
        "=== RECENT MAINTENANCE HISTORY ===\n"
        f"{_history_block(bundle)}\n\n"
        "=== BUSINESS CONSTRAINTS ===\n"
        f"{_business_block(bundle)}\n\n"
        "=== OPERATOR REPORT ==="
        f"\n{bundle.business.operator_report or 'none'}\n\n"
        "=== MANUAL CONDITION ==="
        f"\n{bundle.manual_condition or 'none'}"
    )


def _defects_block(bundle: ContextBundle) -> str:
    if not bundle.defects:
        return "=== VISUAL INSPECTION ===\n(no images inspected)\n\n"
    lines = ["=== VISUAL INSPECTION ==="]
    defect_rate = bundle.defect_rate
    lines.append(f"defect_rate: {defect_rate:.0%} ({sum(1 for d in bundle.defects if d.label == 'defect')} of {len(bundle.defects)})")
    for d in bundle.defects:
        region_str = f" region=({d.region[0]},{d.region[1]},{d.region[2]},{d.region[3]})" if d.region else ""
        lines.append(
            f"- {d.image}: score={d.score:.3f}, threshold={d.threshold:.3f}, "
            f"label={d.label}, severity={d.severity}{region_str}"
            + (f", class={d.defect_class} ({d.class_confidence:.0%})" if d.defect_class else "")
        )
    return "\n".join(lines) + "\n\n"


def _failure_mode_block(bundle: ContextBundle) -> str:
    """What the defect classes imply, and what the sensors did or did not confirm.

    Stated as proposals with their evidence rather than conclusions: the model
    must not treat an uncorroborated candidate as an established cause.
    """
    if not bundle.failure_modes:
        return ""
    lines = [
        "=== DEFECT -> FAILURE MODE (engineering table, not learned) ===",
        "A candidate is a hypothesis. Only escalate one the sensors corroborate;",
        "say plainly when none is corroborated.",
    ]
    for link in bundle.failure_modes:
        confirmed = ", ".join(link.corroborated_by) if link.corroborated_by else "NONE"
        lines.append(
            f"- {link.defect_class} x{link.images} -> candidates: {', '.join(link.failure_modes)}"
            f" | corroborated by: {confirmed} | priority_delta: {link.priority_delta:+d}"
            + (f" | action: {link.recommended_action}" if link.recommended_action else "")
            + (f" | source: {link.source}" if link.source else "")
        )
    return "\n".join(lines) + "\n\n"


def _qc_block(bundle: ContextBundle, asset_id: str) -> str:
    if not bundle.qc_by_phase:
        return ""
    lines = ["=== PRODUCT QC BY PHASE ==="]
    for q in bundle.qc_by_phase:
        tag = "<-- THIS ASSET" if q.asset_id == asset_id else "<-- upstream"
        lines.append(
            f"{q.phase} (asset: {q.asset_id}, product: {q.product}) {tag}: "
            f"{q.defects}/{q.inspected} defects ({q.defect_rate:.0%})"
        )
    return "\n".join(lines) + "\n\n"


def build_user_turn(bundle: ContextBundle, tier, asset_id: str = "") -> str:
    return (
        f"{_context_str(bundle, asset_id)}\n\n"
        f"Tier: {tier}\n"
        "Produce the maintenance analysis JSON for this asset."
    )


def build_ask_turn(bundle: ContextBundle, question: str, asset_id: str = "") -> str:
    return (
        f"{_context_str(bundle, asset_id)}\n\n"
        f"Question: {question}\n"
        "Answer the question using the provided context. Cite documents by title. "
        "IMPORTANT: ignore the JSON output rule above - return a plain-text answer, "
        "no JSON, no markdown."
    )