"""Validity predicate (FR-004/FR-005). A recorded step is reusable ONLY when its
relevant inputs and model/prompt are provably unchanged. Uncertainty ⇒ not
reusable (fail toward recompute).

Soundness note: the fingerprint is computed over DECLARED predecessors only —
all the tool knows. If a true dependency is undeclared (a missing edge), a
changed hidden input will NOT change this fingerprint, so reuse can be wrongly
judged valid. That residual risk is exactly what the benchmark measures; it is
never hidden."""

from __future__ import annotations

import hashlib

from replaygate.graph.dag import DependencyGraph


def fingerprint(node: str, model_id: str, prompt_id: str,
                pred_outputs: dict[str, str]) -> str:
    """Canonical fingerprint over a node's declared-predecessor outputs + its model/prompt."""
    parts = [node, model_id, prompt_id]
    for p in sorted(pred_outputs):
        parts.append(f"{p}={pred_outputs[p]}")
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


def reusable(node: str, graph: DependencyGraph, recorded_fp: str,
             current_outputs: dict[str, str], eff_model: str, eff_prompt: str):
    """Return (is_reusable, justification)."""
    preds = graph.predecessors(node)
    pred_out = {}
    for p in preds:
        if p not in current_outputs:
            return False, f"predecessor {p!r} output unavailable (uncertain) → recompute"
        pred_out[p] = current_outputs[p]
    fp = fingerprint(node, eff_model, eff_prompt, pred_out)
    if fp == recorded_fp:
        return True, "declared inputs + model/prompt unchanged"
    return False, "declared input/model/prompt changed → recompute"
