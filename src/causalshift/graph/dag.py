"""Dependency DAG over workflow nodes + causal closure (research.md)."""

from __future__ import annotations

import networkx as nx

from causalshift.models import Workflow


class DependencyGraph:
    def __init__(self, workflow: Workflow):
        self.g = nx.DiGraph()
        self.g.add_nodes_from(workflow.nodes)
        self.g.add_edges_from(workflow.edges)
        if not nx.is_directed_acyclic_graph(self.g):
            raise ValueError("workflow graph is cyclic; out of contract (DAG-only)")

    def predecessors(self, node: str) -> list[str]:
        return list(self.g.predecessors(node))

    def topo_order(self) -> list[str]:
        return list(nx.topological_sort(self.g))

    def terminal_nodes(self) -> list[str]:
        return [n for n in self.g.nodes if self.g.out_degree(n) == 0]

    def affected_set(self, targets: list[str]) -> set[str]:
        """Intervention targets plus all their descendants (declared closure)."""
        affected: set[str] = set()
        for t in targets:
            if t not in self.g:
                raise ValueError(f"intervention targets unknown node {t!r}")
            affected.add(t)
            affected.update(nx.descendants(self.g, t))
        return affected
