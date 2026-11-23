"""Injected-fault corpus with known ground truth (data-model.md BenchmarkCase).

Synthetic numeric agents (no LLM). Topology per case:

    root ──▶ mid ──▶ leaf        (declared chain; terminal = leaf)
    root ──▶ side                (declared; side has no declared child)

`root` is a per-trajectory source input (never recomputed, always reused).
Signals: mid = base + root + delta(mid, model); leaf = base + mid [+ side if a
hidden edge exists] + delta(leaf, model); side = base + root + delta(side, model).

Three case kinds:
  - normal regressing : intervene `mid`→bad model. leaf is a DECLARED descendant,
    so selective recomputes it and agrees with full. (no false negative)
  - missing-edge regressing : `leaf` TRULY depends on `side` (hidden edge, NOT in
    the declared graph); intervene `side`→bad model. Selective sees `side` with no
    declared descendants, reuses stale `leaf`, and MISSES the regression that full
    catches. (a measured false negative)
  - non-regressing : intervene `mid`→neutral model (delta 0). Neither detects. (agreement)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from causalshift.backends.fixture import FixtureBackend
from causalshift.models import (
    Cost, GroundTruth, Intervention, Step, Trajectory, Workflow,
)
from causalshift.replay.validity import fingerprint

NODES = ["root", "mid", "side", "leaf"]
DECLARED_EDGES = [("root", "mid"), ("mid", "leaf"), ("root", "side")]
BASE = {"root": 0.0, "mid": 1.0, "side": 1.0, "leaf": 1.0}
BAD_DELTA = -5.0   # a 'bad' model's drop, large enough for a clear CI


@dataclass
class CaseSpec:
    case_id: str
    workflow: Workflow
    intervention: Intervention
    fault_node: str | None
    regresses: bool
    missing_edge: bool
    backend: FixtureBackend


def _declared_preds(node: str) -> list[str]:
    return [s for s, d in DECLARED_EDGES if d == node]


def _baseline_signal(node: str, roots: dict[str, float], hidden: bool) -> float:
    # baseline = model "A", delta 0 everywhere; computed in dependency order
    r = roots["root"]
    if node == "root":
        return r
    if node == "side":
        return BASE["side"] + r
    if node == "mid":
        return BASE["mid"] + r
    if node == "leaf":
        mid = BASE["mid"] + r
        side = BASE["side"] + r
        return BASE["leaf"] + mid + (side if hidden else 0.0)
    return 0.0


def _make_case(case_id: str, kind: str, m_trajectories: int, rng) -> CaseSpec:
    hidden = kind == "missing_edge"
    if kind == "normal":
        fault_node, bad_model, regresses = "mid", "B", True
    elif kind == "missing_edge":
        fault_node, bad_model, regresses = "side", "B", True
    else:  # non_regressing
        fault_node, bad_model, regresses = "mid", "C", False

    # true dependency structure (what the agent really reads)
    true_deps = {"mid": ["root"], "side": ["root"],
                 "leaf": ["mid"] + (["side"] if hidden else [])}
    model_delta = {(fault_node, bad_model): (BAD_DELTA if regresses else 0.0)}
    backend = FixtureBackend(true_deps=true_deps, base=BASE, model_delta=model_delta)
    backend.sources = {"root"}  # consumed by FixtureBackend.recompute

    trajectories = []
    for i in range(m_trajectories):
        roots = {"root": float(rng.normal(10.0, 1.0))}
        steps = []
        current = {"root": f"{roots['root']:.6f}"}
        for idx, node in enumerate(NODES):
            sig = _baseline_signal(node, roots, hidden)
            current[node] = f"{sig:.6f}"
        for idx, node in enumerate(NODES):
            preds = {p: current[p] for p in _declared_preds(node)}
            fp = fingerprint(node, "A", "p0", preds)
            steps.append(Step(step_index=idx, node_name=node,
                              input_fingerprint=fp, output=current[node],
                              model_id="A", prompt_id="p0",
                              cost=Cost(tokens=10, latency_ms=1.0)))
        trajectories.append(Trajectory(
            trajectory_id=f"{case_id}-t{i}", workflow_id=case_id, steps=steps,
            ground_truth=GroundTruth(fault_node=fault_node if regresses else None,
                                     regresses=regresses)))

    workflow = Workflow(workflow_id=case_id, nodes=list(NODES),
                        edges=list(DECLARED_EDGES), trajectories=trajectories)
    intervention = Intervention(workflow_id=case_id,
                                targets={fault_node: {"model_id": bad_model}})
    return CaseSpec(case_id, workflow, intervention, fault_node if regresses else None,
                    regresses, hidden, backend)


def make_corpus(seed: int = 1729, n_normal: int = 30, n_missing: int = 1,
                n_nonreg: int = 10, m_trajectories: int = 30) -> list[CaseSpec]:
    rng = np.random.default_rng(seed)
    cases: list[CaseSpec] = []
    for i in range(n_normal):
        cases.append(_make_case(f"normal-{i}", "normal", m_trajectories, rng))
    for i in range(n_missing):
        cases.append(_make_case(f"missing-{i}", "missing_edge", m_trajectories, rng))
    for i in range(n_nonreg):
        cases.append(_make_case(f"nonreg-{i}", "non_regressing", m_trajectories, rng))
    return cases


def case_to_input_dict(case: CaseSpec) -> dict:
    wf = case.workflow
    return {
        "workflow_id": wf.workflow_id,
        "graph": {"nodes": wf.nodes, "edges": [list(e) for e in wf.edges]},
        "trajectories": [{
            "trajectory_id": t.trajectory_id,
            "steps": [{
                "step_index": s.step_index, "node_name": s.node_name,
                "input_fingerprint": s.input_fingerprint, "output": s.output,
                "model_id": s.model_id, "prompt_id": s.prompt_id,
                "cost": {"tokens": s.cost.tokens, "latency_ms": s.cost.latency_ms},
            } for s in t.steps],
            "ground_truth": {"fault_node": t.ground_truth.fault_node,
                             "regresses": t.ground_truth.regresses},
        } for t in wf.trajectories],
    }
