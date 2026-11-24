"""Trace-input validation (contracts/trace-input.md). Fail closed on out-of-contract input."""

from __future__ import annotations

import networkx as nx

from replaygate.models import Workflow


class TraceInputError(ValueError):
    """Raised for out-of-contract input; CLI maps this to a clear non-zero exit."""


def validate_workflow(wf: Workflow) -> None:
    node_set = set(wf.nodes)
    if len(node_set) != len(wf.nodes):
        raise TraceInputError("duplicate node names in graph.nodes")

    for src, dst in wf.edges:
        if src not in node_set or dst not in node_set:
            raise TraceInputError(f"edge ({src}->{dst}) references an undeclared node")

    g = nx.DiGraph()
    g.add_nodes_from(wf.nodes)
    g.add_edges_from(wf.edges)
    if not nx.is_directed_acyclic_graph(g):
        raise TraceInputError("graph is cyclic; ReplayGate v1 supports DAG agents only")

    for traj in wf.trajectories:
        seen_nodes = set()
        for step in traj.steps:
            if step.node_name not in node_set:
                raise TraceInputError(
                    f"trajectory {traj.trajectory_id}: step references undeclared node "
                    f"{step.node_name!r}"
                )
            if step.node_name in seen_nodes:
                raise TraceInputError(
                    f"trajectory {traj.trajectory_id}: node {step.node_name!r} visited "
                    f"twice (loops are out of contract)"
                )
            seen_nodes.add(step.node_name)
            if not step.input_fingerprint:
                raise TraceInputError(
                    f"trajectory {traj.trajectory_id}: step {step.node_name!r} is missing "
                    f"input_fingerprint (required for sound reuse)"
                )
