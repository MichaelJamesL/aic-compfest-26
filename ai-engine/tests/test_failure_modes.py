"""The restraint rule: a defect proposes, a sensor disposes."""
import datetime

from src import failure_modes
from src.schemas import SensorReading

NOW = datetime.datetime(2026, 8, 25, tzinfo=datetime.timezone.utc)


def series(tag, values):
    return [
        SensorReading(tag=tag, value=v, unit="", recorded_at=NOW + datetime.timedelta(minutes=i))
        for i, v in enumerate(values)
    ]


def test_corroborated_defect_may_escalate():
    link = failure_modes.links(["thread_side"], series("torque_nm", [10.0 + i for i in range(20)]))[0]
    assert link.failure_modes == ["tool_wear", "axis_backlash"]
    assert link.corroborated_by == ["torque_nm"]
    assert link.priority_delta == 1
    assert link.source


def test_uncorroborated_defect_is_reported_but_never_escalates():
    link = failure_modes.links(["thread_side"], series("torque_nm", [10.0] * 20))[0]
    # still reported — the coordinator should see the hypothesis
    assert link.failure_modes == ["tool_wear", "axis_backlash"]
    assert link.corroborated_by == []
    assert link.priority_delta == 0


def test_a_defect_with_no_signal_to_check_stays_at_zero():
    """scratch_head is usually handling, not the machine. The table says so."""
    link = failure_modes.links(["scratch_head"], series("torque_nm", [10.0 + i for i in range(20)]))[0]
    assert link.priority_delta == 0


def test_missing_tag_is_not_corroboration():
    link = failure_modes.links(["thread_top"], series("unrelated_tag", [1.0] * 20))[0]
    assert link.corroborated_by == []
    assert link.priority_delta == 0


def test_good_and_unknown_classes_produce_no_links():
    assert failure_modes.links(["good", "invented_class"], series("torque_nm", [1.0] * 20)) == []


def test_repeated_class_is_counted_once_with_its_tally():
    links = failure_modes.links(["thread_top", "thread_top", "thread_side"], series("torque_nm", [1.0] * 20))
    assert {link.defect_class: link.images for link in links} == {"thread_top": 2, "thread_side": 1}


def test_context_carries_classes_into_failure_modes(monkeypatch):
    """The wiring: detector flags, classifier names, table maps, engine escalates."""
    from src import classify, context, knowledge, vision
    from src.schemas import AnalysisRequest, Asset, DefectFinding, Tier

    monkeypatch.setattr(knowledge, "search", lambda *a, **k: [])
    monkeypatch.setattr(vision, "inspect", lambda *a, **k: [
        DefectFinding(image="a.png", score=0.9, threshold=0.5, label="defect", severity="high"),
        DefectFinding(image="b.png", score=0.1, threshold=0.5, label="ok", severity="low"),
    ])
    # only the flagged image is classified
    monkeypatch.setattr(classify, "classify", lambda paths: [("thread_side", 0.91)] * len(paths))

    bundle = context.select_context(AnalysisRequest(
        tier=Tier.PROFESSIONAL,
        asset=Asset(id="mill-1", type="cnc-mill"),
        images=["a.png", "b.png"],
        readings=series("torque_nm", [10.0 + i for i in range(20)]),
    ))

    assert [d.defect_class for d in bundle.defects] == ["thread_side", None]
    assert bundle.defects[0].class_confidence == 0.91
    link = bundle.failure_modes[0]
    assert link.defect_class == "thread_side"
    assert link.corroborated_by == ["torque_nm"]
    assert link.priority_delta == 1
