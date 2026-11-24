"""US1: sound full-re-execution verdict with CIs."""

import numpy as np

from replaygate.evaluate.quality import TerminalSignalEvaluator
from replaygate.graph.dag import DependencyGraph
from replaygate.replay.engine import full_replay
from replaygate.report.verdict import build_verdict
from benchmark.faults.inject import _make_case

EVAL = TerminalSignalEvaluator(target="leaf")


def _verdict(case):
    g = DependencyGraph(case.workflow)
    res = [full_replay(t, g, case.intervention, case.backend, EVAL)
           for t in case.workflow.trajectories]
    return build_verdict(case.case_id, "full", res)


def test_regressing_case_detected():
    case = _make_case("c", "normal", 30, np.random.default_rng(0))
    v = _verdict(case)
    assert v.regressed
    assert v.ci_high < 0            # CI entirely below zero
    assert v.reuse_exposure is None  # full mode never reuses


def test_non_regressing_case_not_flagged():
    case = _make_case("c", "non_regressing", 30, np.random.default_rng(0))
    v = _verdict(case)
    assert not v.regressed
