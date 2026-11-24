"""Capture a CausalShift trace from a compiled LangGraph app — near-zero code.

    from causalshift.adapters.langgraph import trace_from_langgraph
    app = graph.compile()
    trace = trace_from_langgraph(app, inputs=[{"q": q} for q in questions])
    # -> ingest with store.workflow_from_dict(trace) or dump to JSON for the CLI

How it works: the compiled graph's nodes/edges give the declared dependency DAG,
and `app.stream(input, stream_mode="updates")` yields each node's output as it
runs, so inputs/outputs/fingerprints are captured automatically.

HONEST CAVEAT (soundness): LangGraph nodes read a SHARED state object, so a
node's true inputs can include state written by non-adjacent nodes. Using the
graph's control-flow edges as the declared dependency edges therefore
UNDER-declares data dependencies — the classic missing-edge risk. CausalShift
does not hide this: it is exactly what `reuse_exposure` and the benchmark's
false-negative rate measure. For nodes with hidden cross-state reads, prefer the
explicit `InstrumentedAgent` seam (declare deps yourself) or add the missing
edges to the captured graph before ingest. v1 supports DAG graphs only (a node
revisited in a loop is rejected by validation)."""

from __future__ import annotations

import json

from causalshift.replay.validity import fingerprint

_SPECIAL = {"__start__", "__end__"}


def trace_from_langgraph(app, inputs, workflow_id: str = "langgraph",
                         model_id: str = "node", prompt_id: str = "default") -> dict:
    """Run a compiled LangGraph `app` over each input and return a CausalShift
    trace dict (contract: trace-input.md). `inputs` is a list of initial states."""
    drawable = app.get_graph()
    real = [n for n in drawable.nodes if n not in _SPECIAL]
    edges = [(e.source, e.target) for e in drawable.edges
             if e.source in real and e.target in real]
    preds = {n: [s for s, t in edges if t == n] for n in real}

    trajectories = []
    for i, inp in enumerate(inputs):
        outputs: dict[str, str] = {}
        steps: list[dict] = []
        for chunk in app.stream(inp, stream_mode="updates"):
            for node, update in chunk.items():
                if node not in real:
                    continue
                out = json.dumps(update, default=str, sort_keys=True)
                p = {d: outputs[d] for d in preds[node] if d in outputs}
                steps.append({
                    "step_index": len(steps), "node_name": node,
                    "input_fingerprint": fingerprint(node, model_id, prompt_id, p),
                    "output": out, "model_id": model_id, "prompt_id": prompt_id,
                    "cost": {"tokens": max(1, len(out) // 4), "latency_ms": 0.0},
                })
                outputs[node] = out
        trajectories.append({"trajectory_id": f"{workflow_id}-t{i}", "steps": steps})

    return {
        "workflow_id": workflow_id,
        "graph": {"nodes": real, "edges": [list(e) for e in edges]},
        "prompts": {},
        "trajectories": trajectories,
    }
