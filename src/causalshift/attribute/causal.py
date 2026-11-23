"""Regression attribution: isolate each targeted node's causal contribution.

For each target, replay with the intervention restricted to that one node and
measure the mean quality delta it alone causes. The most-negative contribution
is the responsible decision. Single-fault first; interacting faults surface as
several negative contributions rather than all credit on one node."""

from __future__ import annotations

from causalshift.evaluate.quality import QualityEvaluator
from causalshift.graph.dag import DependencyGraph
from causalshift.models import Intervention, Trajectory
from causalshift.replay.engine import full_replay


def attribute(trajectories: list[Trajectory], graph: DependencyGraph,
              intervention: Intervention, backend, evaluator: QualityEvaluator):
    """Return [(node, mean_isolated_delta)] sorted most-negative first."""
    contributions: list[tuple[str, float]] = []
    for node, change in intervention.targets.items():
        iso = Intervention(workflow_id=intervention.workflow_id, targets={node: change})
        deltas = [full_replay(t, graph, iso, backend, evaluator).delta
                  for t in trajectories]
        mean = sum(deltas) / len(deltas) if deltas else 0.0
        contributions.append((node, mean))
    contributions.sort(key=lambda x: x[1])   # most negative (worst) first
    return contributions
