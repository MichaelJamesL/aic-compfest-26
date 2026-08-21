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


def _business_block(bundle: ContextBundle) -> str:
    b = bundle.business
    return (
        f"- production_schedule: {b.production_schedule or 'not provided'}\n"
        f"- spareparts: {b.spareparts or 'none listed'}\n"
        f"- sparepart_eta: {b.sparepart_eta or 'not provided'}\n"
        f"- technicians_available: {b.technicians_available if b.technicians_available is not None else 'not provided'}"
    )


def _context_str(bundle: ContextBundle) -> str:
    defects_block = _defects_block(bundle)

    return (
        "=== ASSET FACTS ===\n"
        f"{bundle.assets_facts}\n\n"
        "=== PRECOMPUTED HEALTH ==="
        f"\nhealth_score: {bundle.health_score}\n"
        "anomalies: "
        + (str([a.model_dump() for a in bundle.anomalies]) if bundle.anomalies else "none")
        + "\n\n"
        + defects_block
        + "\n"
        "=== REFERENCE DOCUMENTS (cite by title) ===\n"
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
        )
    return "\n".join(lines) + "\n\n"


def build_user_turn(bundle: ContextBundle, tier) -> str:
    return (
        f"{_context_str(bundle)}\n\n"
        f"Tier: {tier}\n"
        "Produce the maintenance analysis JSON for this asset."
    )


def build_ask_turn(bundle: ContextBundle, question: str) -> str:
    return (
        f"{_context_str(bundle)}\n\n"
        f"Question: {question}\n"
        "Answer the question using the provided context. Cite documents by title. "
        "IMPORTANT: ignore the JSON output rule above - return a plain-text answer, "
        "no JSON, no markdown."
    )