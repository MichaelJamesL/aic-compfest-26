"""A QC batch must reach the prompt and the health score, not just a table.

Images uploaded as a batch land in `qc_by_phase`. Everything that read
`bundle.defects` alone treated them as if no inspection had happened: the prompt
said "(no images inspected)" and the model reported that back as a blocker,
while a 100% defect rate cost the machine no health at all.
"""
import datetime

import pytest

from src import context, knowledge, prompts, vision
from src.schemas import AnalysisRequest, Asset, ContextBundle, DefectFinding, PhaseQC, QCBatch, Tier

NOW = datetime.datetime(2026, 8, 25, tzinfo=datetime.timezone.utc)


def finding(label, severity="high", phase="finishing"):
    return DefectFinding(
        image=f"{label}.png", subject="product", score=0.9 if label == "defect" else 0.1,
        threshold=0.5, label=label, severity=severity, phase=phase,
    )


@pytest.fixture
def batch_bundle(monkeypatch):
    monkeypatch.setattr(knowledge, "search", lambda *a, **k: [])
    monkeypatch.setattr(vision, "inspect", lambda name, images, **k: (
        [] if k.get("subject", "asset") == "asset" else [finding("defect"), finding("defect"), finding("ok", "low")]
    ))
    return context.select_context(AnalysisRequest(
        tier=Tier.PROFESSIONAL,
        asset=Asset(id="mill-1", type="cnc-mill"),
        qc_batches=[QCBatch(phase="finishing", asset_id="mill-1", product="nut", images=["a.png", "b.png", "c.png"])],
    ))


def test_batch_findings_are_part_of_the_bundle(batch_bundle):
    assert batch_bundle.defects == []          # nothing arrived asset-level
    assert len(batch_bundle.all_findings) == 3
    assert batch_bundle.defect_rate == pytest.approx(2 / 3)


def test_the_prompt_does_not_claim_nothing_was_inspected(batch_bundle):
    block = prompts._defects_block(batch_bundle)
    assert "(no images inspected)" not in block
    assert "defect_rate: 67% (2 of 3)" in block
    # per-image detail, which is what "defect details" means to the model
    assert block.count("label=defect") == 2
    assert "phase=finishing" in block


def test_a_defective_batch_costs_the_machine_health(batch_bundle, monkeypatch):
    monkeypatch.setattr(knowledge, "search", lambda *a, **k: [])
    monkeypatch.setattr(vision, "inspect", lambda *a, **k: [])
    clean = context.select_context(AnalysisRequest(
        tier=Tier.PROFESSIONAL, asset=Asset(id="mill-1", type="cnc-mill"),
    ))
    assert clean.health_score == 100
    # two high-severity defects, at the weight signals.py assigns them
    assert batch_bundle.health_score < clean.health_score


def test_defect_rate_still_reads_asset_level_findings():
    bundle = ContextBundle(
        assets_facts="", anomalies=[], health_score=100, corpus=[], history=[],
        business=__import__("src.schemas", fromlist=["BusinessContext"]).BusinessContext(),
        defects=[finding("defect", phase=None), finding("ok", "low", phase=None)],
        qc_by_phase=[PhaseQC(phase="p", asset_id="a", product="n", inspected=1, defects=1,
                             defect_rate=1.0, findings=[finding("defect")])],
    )
    # both sources counted, not one or the other
    assert len(bundle.all_findings) == 3
    assert bundle.defect_rate == pytest.approx(2 / 3)
