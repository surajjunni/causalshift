"""Full re-execution (sound baseline) and dependency-aware selective replay."""

from __future__ import annotations

from causalshift.backends.base import RecomputeBackend, Unavailable
from causalshift.evaluate.quality import QualityEvaluator
from causalshift.graph.dag import DependencyGraph
from causalshift.models import (
    RECOMPUTED, REUSED, Intervention, ReplayDecision, ReplayResult, Trajectory,
)
from causalshift.replay.validity import reusable


def _effective(intervention, node, rm, rp):
    return intervention.effective(node, rm, rp)


def full_replay(traj: Trajectory, graph: DependencyGraph, intervention: Intervention,
                backend: RecomputeBackend, evaluator: QualityEvaluator) -> ReplayResult:
    """Recompute EVERY node to a fixpoint — never reuses, so it is sound regardless
    of whether the declared graph omits a true edge. The correctness oracle."""
    recorded = traj.output_map()
    models = traj.models()
    baseline = evaluator.score(recorded, graph)
    current = dict(recorded)
    order = [n for n in graph.topo_order() if n in recorded]
    calls = tokens = 0
    latency = 0.0
    inconclusive = False

    for _ in range(len(order) + 1):
        changed = False
        for node in order:
            rm, rp = models.get(node, ("default", "default"))
            em, ep = _effective(intervention, node, rm, rp)
            out = backend.recompute(node, em, ep, current, graph.predecessors(node))
            if isinstance(out, Unavailable):
                inconclusive = True
                continue
            calls += 1
            tokens += out.cost.tokens
            latency += out.cost.latency_ms
            if current.get(node) != out.output:
                current[node] = out.output
                changed = True
        if not changed:
            break

    decisions = [ReplayDecision(s.step_index, s.node_name, RECOMPUTED,
                                "full re-execution", True) for s in traj.steps]
    quality = evaluator.score(current, graph)
    return ReplayResult(traj.trajectory_id, "full", decisions, current, quality,
                        baseline, calls, tokens, latency, inconclusive)


def selective_replay(traj: Trajectory, graph: DependencyGraph, intervention: Intervention,
                     backend: RecomputeBackend, evaluator: QualityEvaluator) -> ReplayResult:
    """Recompute only causally-affected nodes (+ validity escalations); reuse the rest."""
    recorded = traj.output_map()
    models = traj.models()
    fp_map = {s.node_name: s.input_fingerprint for s in traj.steps}
    step_idx = {s.node_name: s.step_index for s in traj.steps}
    baseline = evaluator.score(recorded, graph)
    affected = graph.affected_set(list(intervention.targets))

    current = dict(recorded)
    decisions: list[ReplayDecision] = []
    calls = tokens = 0
    latency = 0.0
    inconclusive = False

    for node in graph.topo_order():
        if node not in recorded and node not in affected:
            continue
        rm, rp = models.get(node, ("default", "default"))
        em, ep = _effective(intervention, node, rm, rp)
        idx = step_idx.get(node, -1)

        if node in affected:
            out = backend.recompute(node, em, ep, current, graph.predecessors(node))
            if isinstance(out, Unavailable):
                inconclusive = True
                decisions.append(ReplayDecision(idx, node, RECOMPUTED,
                    f"in affected set; backend unavailable → inconclusive ({out.reason})", True))
                continue
            calls += 1
            tokens += out.cost.tokens
            latency += out.cost.latency_ms
            current[node] = out.output
            decisions.append(ReplayDecision(idx, node, RECOMPUTED, "in affected set", True))
            continue

        ok, why = reusable(node, graph, fp_map.get(node, ""), current, em, ep)
        if ok:
            decisions.append(ReplayDecision(idx, node, REUSED, why, False, True))
        else:
            out = backend.recompute(node, em, ep, current, graph.predecessors(node))
            if isinstance(out, Unavailable):
                inconclusive = True
                decisions.append(ReplayDecision(idx, node, RECOMPUTED,
                    f"escalated ({why}); backend unavailable → inconclusive", False, False))
                continue
            calls += 1
            tokens += out.cost.tokens
            latency += out.cost.latency_ms
            current[node] = out.output
            decisions.append(ReplayDecision(idx, node, RECOMPUTED, f"escalated: {why}", False, False))

    quality = evaluator.score(current, graph)
    return ReplayResult(traj.trajectory_id, "selective", decisions, current, quality,
                        baseline, calls, tokens, latency, inconclusive)
