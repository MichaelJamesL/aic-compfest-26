"""Build the context bundle that feeds the LLM.

Deterministic by construction: retrieval query, anomaly detection, health
score, and history selection are all stable, and the corpus is packed to a
token budget with a stable ordering so DeepSeek's prefix cache can hit.
"""
from __future__ import annotations

import tiktoken

from . import classify, config, failure_modes, knowledge, vision
from .schemas import AnalysisRequest, ContextBundle, ContextDoc, PhaseQC
from .signals import detect_anomalies, health_score

# How many most-recent maintenance records to include.
HISTORY_LIMIT = 8
# How many documents to retrieve from the knowledge base.
RETRIEVAL_K = 5

_ENC = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_ENC.encode(text))


def _retrieval_query(request: AnalysisRequest) -> str:
    parts = [request.asset.name, request.asset.type]
    if request.business.operator_report:
        parts.append(request.business.operator_report)
    if request.images:
        parts.append("visual inspection defect detection")
    return " ".join(p for p in parts if p).strip()


def _assets_facts(request: AnalysisRequest, anomalies: list, health: int, summary: str, defects: list | None = None) -> str:
    specs = ", ".join(f"{k}={v}" for k, v in request.asset.specs.items()) or "none"
    base = (
        f"{request.asset.name} ({request.asset.type}), criticality={request.asset.criticality}, "
        f"specs: {specs}, anomalies: {len(anomalies)}, health_score={health}. "
        f"Health summary: {summary}"
    )
    if defects:
        defect_count = sum(1 for d in defects if d.label == "defect")
        base += f" Defects: {defect_count} of {len(defects)} images flagged."
    return base


def _pack_corpus(docs: list[ContextDoc], budget_tokens: int) -> list[ContextDoc]:
    """Drop the longest docs until the total fits the budget. Stable order."""
    if budget_tokens <= 0:
        return []
    kept: list[ContextDoc] = []
    running = 0
    for doc in sorted(docs, key=lambda d: _count_tokens(d.text), reverse=True):
        cost = _count_tokens(f"DOC: {doc.title} ({doc.kind})\n{doc.text}")
        if running + cost > budget_tokens:
            continue
        kept.append(doc)
        running += cost
    return sorted(kept, key=lambda d: d.title)


def select_context(
    request: AnalysisRequest, budget_tokens: int | None = None
) -> ContextBundle:
    budget = budget_tokens if budget_tokens is not None else config.CONTEXT_BUDGET_TOKENS

    anomalies = detect_anomalies(request.readings, request.asset.id)
    defects = _classified(vision.inspect(request.asset.id, request.images) if request.images else [])
    health, summary = health_score(request.asset, anomalies, request.history, defects)

    qc_by_phase: list[PhaseQC] = []
    for batch in request.qc_batches:
        if not batch.images:
            continue
        try:
            findings = _classified(vision.inspect(
                batch.product, batch.images, subject="product", phase=batch.phase
            ))
        except (FileNotFoundError, OSError):
            continue
        if not findings:
            # Nothing was inspected — no model, or none of the images could be
            # read. A phase row of "inspected: 0" reads as a clean inspection.
            continue
        defect_count = sum(1 for f in findings if f.label == "defect")
        qc_by_phase.append(
            PhaseQC(
                phase=batch.phase,
                asset_id=batch.asset_id,
                product=batch.product,
                inspected=len(findings),
                defects=defect_count,
                defect_rate=defect_count / len(findings) if findings else 0.0,
                findings=findings,
            )
        )

    # Which defect, then what it implies about the machine — proposals only,
    # until a sensor rule in the table actually holds.
    classes = [
        finding.defect_class
        for group in (defects, *(phase.findings for phase in qc_by_phase))
        for finding in group
        if finding.defect_class and finding.label == "defect"
    ]
    modes = failure_modes.links(classes, request.readings) if classes else []

    query = _retrieval_query(request)
    corpus = knowledge.search(query, request.asset.id, request.factory_id, k=RETRIEVAL_K)

    history = sorted(request.history, key=lambda r: r.performed_at, reverse=True)[
        :HISTORY_LIMIT
    ]

    return ContextBundle(
        assets_facts=_assets_facts(request, anomalies, health, summary, defects),
        anomalies=anomalies,
        defects=defects,
        qc_by_phase=qc_by_phase,
        failure_modes=modes,
        health_score=health,
        corpus=_pack_corpus(corpus, budget),
        history=history,
        business=request.business,
        manual_condition=request.manual_condition,
    )


def _classified(findings):
    """Attach a defect class to each finding, when a classifier is available.

    Only the images the detector flagged are classified: the classifier is the
    expensive half, and a class on an image nothing was wrong with is noise.
    """
    flagged = [f for f in findings if f.label == "defect"]
    if not flagged:
        return findings
    predictions = classify.classify([f.image for f in flagged])
    for finding, (name, confidence) in zip(flagged, predictions):
        finding.defect_class = name
        finding.class_confidence = round(confidence, 3)
    return findings
