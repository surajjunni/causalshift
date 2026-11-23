"""Quality evaluator: scores a candidate output map. Pluggable and applied
IDENTICALLY to baseline and candidate (spec Assumptions)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from causalshift.graph.dag import DependencyGraph


@runtime_checkable
class QualityEvaluator(Protocol):
    def score(self, outputs: dict[str, str], graph: DependencyGraph) -> float:
        ...


class TerminalSignalEvaluator:
    """Numeric evaluator: quality = signal at the designated response node, or the
    mean over declared terminal nodes when none is designated. Higher is better;
    a planted fault lowers the signal. Reading quality at a specific response
    node (not every dangling node) mirrors how a real agent's output is judged."""
    name = "terminal-signal"

    def __init__(self, target: str | None = None):
        self.target = target

    def score(self, outputs: dict[str, str], graph: DependencyGraph) -> float:
        if self.target is not None:
            try:
                return float(outputs.get(self.target, "0"))
            except (TypeError, ValueError):
                return 0.0
        terminals = graph.terminal_nodes()
        vals = []
        for n in terminals:
            try:
                vals.append(float(outputs.get(n, "0")))
            except (TypeError, ValueError):
                vals.append(0.0)
        return sum(vals) / len(vals) if vals else 0.0
