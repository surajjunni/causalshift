"""Reference (full) replay and dependency-aware selective replay.

v0.2 changes (review response):
- full_replay is a single, deterministic topological pass: each node is
  recomputed exactly once, in declared-topological order, consuming its
  predecessors' already-recomputed outputs. It terminates (no fixpoint loop),
  so its call count is a FAIR, well-defined baseline — unlike the earlier
  repeated-until-stable loop, which never converges for stochastic models.
  Soundness scope: it recovers changes that flow along dependencies respected by
  the declared topological order; a truly undeclared back-edge remains a
  known limitation measured by the benchmark.
- selective_replay is now dynamic: a node is recomputed iff it is an
  intervention target OR its declared inputs actually changed (validity
  predicate fails). A descendant whose inputs are unchanged is PRUNED (reused),
  not blindly recomputed. This is the real "recompute only causally-affected
  nodes", not static descendant closure.
"""

from __future__ import annotations

from replaygate.backends.base import RecomputeBackend, Unavailable
from replaygate.evaluate.quality import QualityEvaluator
from replaygate.graph.dag import DependencyGraph
from replaygate.models import (
    RECOMPUTED, REUSED, Intervention, ReplayDecision, ReplayResult, Trajectory,
)
from replaygate.replay.validity import reusable


def full_replay(traj: Trajectory, graph: DependencyGraph, intervention: Intervention,
                backend: RecomputeBackend, evaluator: QualityEvaluator) -> ReplayResult:
    """Single-pass reference replay: recompute every node once in topo order."""
    recorded = traj.output_map()
    models = traj.models()
    baseline = evaluator.score(recorded, graph)
    current = dict(recorded)
    calls = tokens = 0
    latency = 0.0
    inconclusive = False
    decisions = []

    for node in [n for n in graph.topo_order() if n in recorded]:
        rm, rp = models.get(node, ("default", "default"))
        em, ep = intervention.effective(node, rm, rp)
        out = backend.recompute(node, em, ep, current, graph.predecessors(node))
        if isinstance(out, Unavailable):
            inconclusive = True
            decisions.append(ReplayDecision(
                -1, node, RECOMPUTED,
                f"reference recompute unavailable → inconclusive ({out.reason})", True))
            continue
        calls += 1
        tokens += out.cost.tokens
        latency += out.cost.latency_ms
        current[node] = out.output
        decisions.append(ReplayDecision(-1, node, RECOMPUTED, "reference re-execution", True))

    quality = evaluator.score(current, graph)
    return ReplayResult(traj.trajectory_id, "full", decisions, current, quality,
                        baseline, calls, tokens, latency, inconclusive)


def selective_replay(traj: Trajectory, graph: DependencyGraph, intervention: Intervention,
                     backend: RecomputeBackend, evaluator: QualityEvaluator) -> ReplayResult:
    """Dynamic selective replay: recompute targets and any node whose declared
    inputs actually changed; reuse (prune) everything else."""
    recorded = traj.output_map()
    models = traj.models()
    fp_map = {s.node_name: s.input_fingerprint for s in traj.steps}
    step_idx = {s.node_name: s.step_index for s in traj.steps}
    targets = set(intervention.targets)
    baseline = evaluator.score(recorded, graph)

    current = dict(recorded)
    decisions: list[ReplayDecision] = []
    calls = tokens = 0
    latency = 0.0
    inconclusive = False

    def _recompute(node, em, ep, reason, is_target):
        nonlocal calls, tokens, latency, inconclusive
        out = backend.recompute(node, em, ep, current, graph.predecessors(node))
        idx = step_idx.get(node, -1)
        if isinstance(out, Unavailable):
            inconclusive = True
            decisions.append(ReplayDecision(idx, node, RECOMPUTED,
                f"{reason}; backend unavailable → inconclusive ({out.reason})", is_target))
            return
        calls += 1
        tokens += out.cost.tokens
        latency += out.cost.latency_ms
        current[node] = out.output
        decisions.append(ReplayDecision(idx, node, RECOMPUTED, reason, is_target))

    for node in graph.topo_order():
        if node not in recorded and node not in targets:
            continue
        rm, rp = models.get(node, ("default", "default"))
        em, ep = intervention.effective(node, rm, rp)
        idx = step_idx.get(node, -1)

        if node in targets:
            _recompute(node, em, ep, "intervention target", True)
            continue

        ok, why = reusable(node, graph, fp_map.get(node, ""), current, em, ep)
        if ok:
            decisions.append(ReplayDecision(idx, node, REUSED, f"pruned: {why}", False, True))
        else:
            # an upstream recompute changed this node's declared input → recompute
            _recompute(node, em, ep, f"input changed: {why}", False)

    quality = evaluator.score(current, graph)
    return ReplayResult(traj.trajectory_id, "selective", decisions, current, quality,
                        baseline, calls, tokens, latency, inconclusive)
