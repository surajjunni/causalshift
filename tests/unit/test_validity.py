from causalshift.graph.dag import DependencyGraph
from causalshift.models import Workflow
from causalshift.replay.validity import fingerprint, reusable

WF = Workflow("w", ["root", "mid", "leaf"], [("root", "mid"), ("mid", "leaf")])
G = DependencyGraph(WF)


def test_reusable_when_unchanged():
    preds = {"mid": "5.0"}
    fp = fingerprint("leaf", "A", "p", preds)
    ok, why = reusable("leaf", G, fp, {"mid": "5.0"}, "A", "p")
    assert ok and "unchanged" in why


def test_not_reusable_when_input_changed():
    fp = fingerprint("leaf", "A", "p", {"mid": "5.0"})
    ok, _ = reusable("leaf", G, fp, {"mid": "9.0"}, "A", "p")
    assert not ok


def test_not_reusable_when_model_changed():
    fp = fingerprint("leaf", "A", "p", {"mid": "5.0"})
    ok, _ = reusable("leaf", G, fp, {"mid": "5.0"}, "B", "p")
    assert not ok


def test_uncertain_predecessor_fails_toward_recompute():
    fp = fingerprint("leaf", "A", "p", {"mid": "5.0"})
    ok, why = reusable("leaf", G, fp, {}, "A", "p")  # mid missing from current
    assert not ok and "uncertain" in why
