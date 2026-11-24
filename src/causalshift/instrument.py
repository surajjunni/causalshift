"""A light instrumentation seam: wrap an agent's node functions so that running
the agent auto-captures a CausalShift trace (per-node output, input fingerprint,
and the declared dependency edges) with minimal friction.

The dependency edges are declared ONCE per node via the decorator's `deps=` —
that is the deliberate, honest level of instrumentation (the constitution's
"explicitly instrumented DAG"). Inputs, outputs and fingerprints are captured
automatically, and the emitted fingerprints are exactly what the replay
validity predicate consumes, so recorded traces are immediately replayable.

Example
-------
    agent = InstrumentedAgent("support")

    @agent.node("planner", deps=["question"], prompt_id="plan.v1", prompt="Plan...")
    def planner(question): ...

    @agent.node("responder", deps=["planner"], prompt_id="respond.v1", prompt="Answer...")
    def responder(planner): ...

    for q in questions:
        with agent.trajectory(f"t{i}") as run:
            run.set("question", q)     # source input
            run.run_all()              # executes nodes in dependency order, capturing

    agent.save("trace.json")           # trace-input contract, incl. the prompt registry
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable

import networkx as nx

from causalshift.replay.validity import fingerprint

SOURCE_MODEL = "source"
SOURCE_PROMPT = "verbatim"


@dataclass
class _NodeDef:
    name: str
    deps: list[str]
    fn: Callable
    model_id: str
    prompt_id: str


class _Run:
    def __init__(self, agent: "InstrumentedAgent", trajectory_id: str):
        self.agent = agent
        self.trajectory_id = trajectory_id
        self.outputs: dict[str, str] = {}
        self.steps: list[dict] = []

    def set(self, node_name: str, value) -> None:
        """Record a source input (a node with no dependencies)."""
        self.agent._ensure_source(node_name)
        out = str(value)
        self.outputs[node_name] = out
        self._record(node_name, [], out, SOURCE_MODEL, SOURCE_PROMPT)

    def run_all(self) -> dict[str, str]:
        """Execute all decorated nodes in dependency order, capturing each."""
        for name in self.agent._topo_decorated():
            nd = self.agent._nodes[name]
            missing = [d for d in nd.deps if d not in self.outputs]
            if missing:
                raise ValueError(f"node {name!r} missing inputs {missing} "
                                 f"(set sources / order dependencies)")
            out = str(nd.fn(**{d: self.outputs[d] for d in nd.deps}))
            self.outputs[name] = out
            self._record(name, nd.deps, out, nd.model_id, nd.prompt_id)
        return self.outputs

    def _record(self, node, deps, out, model_id, prompt_id) -> None:
        preds = {d: self.outputs[d] for d in deps}
        self.steps.append({
            "step_index": len(self.steps), "node_name": node,
            "input_fingerprint": fingerprint(node, model_id, prompt_id, preds),
            "output": out, "model_id": model_id, "prompt_id": prompt_id,
            "cost": {"tokens": max(1, len(out) // 4), "latency_ms": 0.0},
        })


class InstrumentedAgent:
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self._nodes: dict[str, _NodeDef] = {}     # decorated nodes only
        self._sources: set[str] = set()
        self._prompts: dict[str, str] = {}
        self._trajectories: list[dict] = []

    def node(self, name: str, deps=(), model_id: str = "default",
             prompt_id: str = "default", prompt: str | None = None):
        deps = list(deps)
        if prompt is not None:
            self._prompts[prompt_id] = prompt

        def deco(fn: Callable) -> Callable:
            self._nodes[name] = _NodeDef(name, deps, fn, model_id, prompt_id)
            return fn
        return deco

    def _ensure_source(self, name: str) -> None:
        if name not in self._nodes:
            self._sources.add(name)

    def _all_nodes(self) -> list[str]:
        # sources first (stable), then decorated nodes in declaration order
        return list(dict.fromkeys(list(self._sources) + list(self._nodes)))

    def _edges(self) -> list[tuple[str, str]]:
        return [(d, n) for n, nd in self._nodes.items() for d in nd.deps]

    def _topo_decorated(self) -> list[str]:
        g = nx.DiGraph()
        g.add_nodes_from(self._all_nodes())
        g.add_edges_from(self._edges())
        if not nx.is_directed_acyclic_graph(g):
            raise ValueError("instrumented agent graph is cyclic (DAG-only)")
        return [n for n in nx.topological_sort(g) if n in self._nodes]

    @contextmanager
    def trajectory(self, trajectory_id: str):
        run = _Run(self, trajectory_id)
        yield run
        self._trajectories.append({"trajectory_id": trajectory_id, "steps": run.steps})

    def to_trace_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "graph": {"nodes": self._all_nodes(),
                      "edges": [list(e) for e in self._edges()]},
            "prompts": dict(self._prompts),
            "trajectories": list(self._trajectories),
        }

    def save(self, path: str) -> str:
        import json
        from pathlib import Path
        Path(path).write_text(json.dumps(self.to_trace_dict(), indent=2))
        return path
