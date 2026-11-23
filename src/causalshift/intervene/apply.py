"""Intervention engine: validate targets against the graph."""

from __future__ import annotations

from causalshift.graph.dag import DependencyGraph
from causalshift.models import Intervention


def validate_intervention(intervention: Intervention, graph: DependencyGraph) -> None:
    for node in intervention.targets:
        if node not in graph.g:
            raise ValueError(f"intervention targets unknown node {node!r}")
