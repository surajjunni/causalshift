"""US3: selective replay — sound reuse, escalation, and the measured FN case."""

import numpy as np

from causalshift.evaluate.quality import TerminalSignalEvaluator
from causalshift.graph.dag import DependencyGraph
from causalshift.models import REUSED
from causalshift.replay.engine import full_replay, selective_replay
from causalshift.report.verdict import build_verdict
from benchmark.faults.inject import _make_case

EVAL = TerminalSignalEvaluator(target="leaf")


def _verdicts(case):
    g = DependencyGraph(case.workflow)
    full = build_verdict(case.case_id, "full",
                         [full_replay(t, g, case.intervention, case.backend, EVAL)
                          for t in case.workflow.trajectories])
    sel_res = [selective_replay(t, g, case.intervention, case.backend, EVAL)
               for t in case.workflow.trajectories]
    sel = build_verdict(case.case_id, "selective", sel_res)
    return full, sel, sel_res


def test_selective_agrees_with_full_on_normal_case_and_reuses():
    case = _make_case("c", "normal", 30, np.random.default_rng(2))
    full, sel, sel_res = _verdicts(case)
    assert sel.regressed == full.regressed == True
    # root is a source outside the affected set → it is reused
    assert any(d.action == REUSED and d.node_name == "root" for d in sel_res[0].decisions)
    # selective always reports a false-negative risk (headline)
    assert sel.reuse_exposure is not None


def test_missing_edge_produces_a_false_negative():
    case = _make_case("c", "missing_edge", 30, np.random.default_rng(3))
    full, sel, sel_res = _verdicts(case)
    # full (sound) catches it; selective reuses the hidden-dependent leaf and misses it
    assert full.regressed and not sel.regressed
    assert any(d.action == REUSED and d.node_name == "leaf" for d in sel_res[0].decisions)
