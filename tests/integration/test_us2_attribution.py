"""US2: attribution names the responsible node."""

import numpy as np

from causalshift.attribute.causal import attribute
from causalshift.evaluate.quality import TerminalSignalEvaluator
from causalshift.graph.dag import DependencyGraph
from benchmark.faults.inject import _make_case

EVAL = TerminalSignalEvaluator(target="leaf")


def test_single_fault_attributed_to_faulty_node():
    case = _make_case("c", "normal", 30, np.random.default_rng(1))
    g = DependencyGraph(case.workflow)
    ranked = attribute(case.workflow.trajectories, g, case.intervention, case.backend, EVAL)
    assert ranked[0][0] == case.fault_node   # top (most-negative) == planted fault
    assert ranked[0][1] < 0
