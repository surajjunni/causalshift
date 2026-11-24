"""Deterministic numeric backend for the injected-fault benchmark.

Each node emits a numeric 'signal' (encoded as a string) computed from its TRUE
predecessors' signals plus a per-(node, model) delta. The true dependency
structure lives here, not in the declared graph — so a declared graph that omits
a true edge cannot be caught by reuse, which is exactly the false-negative the
benchmark measures. No LLM is involved, so results are reproducible offline."""

from __future__ import annotations

from replaygate.backends.base import Outcome, Produced
from replaygate.models import Cost


def _to_f(v: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


class FixtureBackend:
    """
    true_deps:   node -> list of true predecessor nodes (may exceed declared edges)
    base:        node -> base signal
    model_delta: (node, model_id) -> additive delta (a 'bad' model lowers signal)
    """
    name = "fixture"

    def __init__(self, true_deps, base, model_delta, sources=None):
        self.true_deps = true_deps
        self.base = base
        self.model_delta = model_delta
        self.sources = set(sources or ())
        self.calls = 0

    def recompute(self, node_name, model_id, prompt_id, current_outputs,
                  predecessors=None) -> Outcome:
        self.calls += 1
        # Sources are per-trajectory inputs, not recomputed: return them unchanged.
        if node_name in self.sources:
            return Produced(output=current_outputs.get(node_name, "0"),
                            cost=Cost(tokens=0, latency_ms=0.0))
        signal = self.base.get(node_name, 0.0)
        for p in self.true_deps.get(node_name, []):
            signal += _to_f(current_outputs.get(p, "0"))
        signal += self.model_delta.get((node_name, model_id), 0.0)
        return Produced(output=f"{signal:.6f}", cost=Cost(tokens=10, latency_ms=1.0))
