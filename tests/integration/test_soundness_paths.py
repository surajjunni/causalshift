"""Review P1: explicit tests for unavailable tools and stochastic behavior."""

import numpy as np

from replaygate.backends.base import Produced, UnavailableBackend
from replaygate.evaluate.quality import TerminalSignalEvaluator
from replaygate.graph.dag import DependencyGraph
from replaygate.models import Cost, RECOMPUTED
from replaygate.replay.engine import full_replay, selective_replay
from replaygate.report.verdict import build_verdict, verdict_exit_code
from benchmark.faults.inject import _make_case

EVAL = TerminalSignalEvaluator(target="leaf")


class _StochasticBackend:
    """Returns a different output on every call — models a nondeterministic LLM."""
    def __init__(self):
        self.calls = 0
        self._rng = np.random.default_rng(0)

    def recompute(self, node, model_id, prompt_id, current_outputs, predecessors=None):
        self.calls += 1
        return Produced(output=f"{self._rng.normal():.6f}", cost=Cost(1, 1.0))


def _case():
    return _make_case("c", "normal", 10, np.random.default_rng(0))


def test_unavailable_backend_is_inconclusive_and_fails_closed():
    case = _case()
    g = DependencyGraph(case.workflow)
    results = [full_replay(t, g, case.intervention, UnavailableBackend(), EVAL)
               for t in case.workflow.trajectories]
    v = build_verdict(case.case_id, "full", results, attribution=None)
    assert v.inconclusive == len(results)        # every trajectory inconclusive
    assert verdict_exit_code(v) == 2             # never a silent pass


def test_selective_target_unavailable_is_inconclusive():
    case = _case()
    g = DependencyGraph(case.workflow)
    r = selective_replay(case.workflow.trajectories[0], g, case.intervention,
                         UnavailableBackend(), EVAL)
    assert r.inconclusive is True


def test_full_replay_terminates_and_recomputes_each_node_once():
    # the fair-baseline fix: a single pass, so a stochastic backend cannot cause
    # a non-terminating fixpoint; call count is exactly one per recorded node.
    case = _case()
    g = DependencyGraph(case.workflow)
    t = case.workflow.trajectories[0]
    backend = _StochasticBackend()
    r = full_replay(t, g, case.intervention, backend, EVAL)
    n_nodes = len(t.output_map())
    assert backend.calls == n_nodes
    assert sum(1 for d in r.decisions if d.action == RECOMPUTED) == n_nodes
