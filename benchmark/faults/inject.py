"""Injected-fault corpus with known, INDEPENDENT ground truth, across multiple
topologies and a tunable hidden-edge frequency (data-model.md BenchmarkCase).

Synthetic numeric agents (no LLM). Each topology designates a per-trajectory
`source`, a `terminal` (the quality node), a `normal_fault` (a declared ancestor
of the terminal) and a `hidden_fault` (a node with a TRUE edge to the terminal
that the DECLARED graph omits). Signals: source = per-trajectory input; every
other node = base + sum(TRUE predecessors) + model delta. Ground truth
(`regresses`) is computed from the TRUE structure at construction — independent
of the replay engine.

Case kinds:
  - normal        : fault on `normal_fault` (declared ancestor) → selective catches.
  - missing_edge  : fault on `hidden_fault` whose edge to the terminal is UNDECLARED
                    → selective reuses the stale terminal and MISSES it (a measured
                    false negative); full catches it (terminal is last in topo).
  - non_regressing: neutral model (delta 0) → neither detects.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
import numpy as np

from causalshift.backends.fixture import FixtureBackend
from causalshift.models import (
    Cost, GroundTruth, Intervention, Step, Trajectory, Workflow,
)
from causalshift.replay.validity import fingerprint

BAD_DELTA = -5.0


@dataclass
class Topology:
    name: str
    nodes: list[str]
    declared_edges: list[tuple]
    source: str
    terminal: str
    normal_fault: str
    hidden_fault: str
    base: dict = field(default_factory=dict)

    def base_of(self, n):
        return self.base.get(n, 1.0)


def _chain():
    return Topology("chain", ["root", "mid", "side", "leaf"],
                    [("root", "mid"), ("mid", "leaf"), ("root", "side")],
                    source="root", terminal="leaf", normal_fault="mid", hidden_fault="side")


def _deepchain():
    return Topology("deepchain", ["root", "a", "b", "c", "leaf", "s"],
                    [("root", "a"), ("a", "b"), ("b", "c"), ("c", "leaf"), ("root", "s")],
                    source="root", terminal="leaf", normal_fault="b", hidden_fault="s")


def _fan():
    return Topology("fan", ["root", "router", "x", "y", "agg", "leaf", "s"],
                    [("root", "router"), ("router", "x"), ("router", "y"),
                     ("x", "agg"), ("y", "agg"), ("agg", "leaf"), ("root", "s")],
                    source="root", terminal="leaf", normal_fault="agg", hidden_fault="s")


TOPOLOGIES = [_chain(), _deepchain(), _fan()]
DEFAULT = _chain()          # back-compat: the original root/mid/side/leaf shape


@dataclass
class CaseSpec:
    case_id: str
    workflow: Workflow
    intervention: Intervention
    fault_node: str | None
    regresses: bool
    missing_edge: bool
    backend: FixtureBackend
    terminal: str = "leaf"


def _true_deps(topo: Topology, hidden: bool) -> dict:
    deps = {n: [] for n in topo.nodes}
    for s, d in topo.declared_edges:
        deps[d].append(s)
    if hidden:
        deps[topo.terminal].append(topo.hidden_fault)   # the UNDECLARED true edge
    return deps


def _declared_preds(topo: Topology, node: str) -> list[str]:
    return [s for s, d in topo.declared_edges if d == node]


def _signals(topo: Topology, true_deps: dict, root_val: float) -> dict:
    g = nx.DiGraph()
    g.add_nodes_from(topo.nodes)
    for n, ps in true_deps.items():
        for p in ps:
            g.add_edge(p, n)
    sig = {}
    for n in nx.topological_sort(g):
        if n == topo.source:
            sig[n] = root_val
        else:
            sig[n] = topo.base_of(n) + sum(sig[p] for p in true_deps[n])
    return sig


def _make_case(case_id: str, kind: str, m_trajectories: int, rng,
               topo: Topology = DEFAULT) -> CaseSpec:
    hidden = kind == "missing_edge"
    if kind == "normal":
        fault, bad, regresses = topo.normal_fault, "B", True
    elif kind == "missing_edge":
        fault, bad, regresses = topo.hidden_fault, "B", True
    else:
        fault, bad, regresses = topo.normal_fault, "C", False

    true_deps = _true_deps(topo, hidden)
    model_delta = {(fault, bad): (BAD_DELTA if regresses else 0.0)}
    backend = FixtureBackend(true_deps=true_deps,
                             base={n: topo.base_of(n) for n in topo.nodes},
                             model_delta=model_delta, sources={topo.source})

    trajectories = []
    for i in range(m_trajectories):
        root_val = float(rng.normal(10.0, 1.0))
        sig = _signals(topo, true_deps, root_val)
        steps = []
        for idx, node in enumerate(topo.nodes):
            preds = {p: f"{sig[p]:.6f}" for p in _declared_preds(topo, node)}
            steps.append(Step(step_index=idx, node_name=node,
                              input_fingerprint=fingerprint(node, "A", "p0", preds),
                              output=f"{sig[node]:.6f}", model_id="A", prompt_id="p0",
                              cost=Cost(tokens=10, latency_ms=1.0)))
        trajectories.append(Trajectory(
            trajectory_id=f"{case_id}-t{i}", workflow_id=case_id, steps=steps,
            ground_truth=GroundTruth(fault_node=fault if regresses else None,
                                     regresses=regresses)))

    workflow = Workflow(workflow_id=case_id, nodes=list(topo.nodes),
                        edges=list(topo.declared_edges), trajectories=trajectories)
    intervention = Intervention(workflow_id=case_id, targets={fault: {"model_id": bad}})
    return CaseSpec(case_id, workflow, intervention, fault if regresses else None,
                    regresses, hidden, backend, terminal=topo.terminal)


def make_corpus(seed: int = 1729, n_normal: int = 30, n_missing: int = 1,
                n_nonreg: int = 10, m_trajectories: int = 30,
                topo: Topology = DEFAULT) -> list[CaseSpec]:
    rng = np.random.default_rng(seed)
    cases: list[CaseSpec] = []
    for i in range(n_normal):
        cases.append(_make_case(f"normal-{i}", "normal", m_trajectories, rng, topo))
    for i in range(n_missing):
        cases.append(_make_case(f"missing-{i}", "missing_edge", m_trajectories, rng, topo))
    for i in range(n_nonreg):
        cases.append(_make_case(f"nonreg-{i}", "non_regressing", m_trajectories, rng, topo))
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
