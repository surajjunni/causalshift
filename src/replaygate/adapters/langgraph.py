"""Capture a ReplayGate trace from a compiled LangGraph app — near-zero code.

    from replaygate.adapters.langgraph import trace_from_langgraph
    app = graph.compile()

    # minimal: every node gets a generic model/prompt id
    trace = trace_from_langgraph(app, inputs=[{"q": q} for q in questions])

    # recommended: give each LLM node its real prompt id + text, so a prompt-change
    # intervention can target one node AND the recompute backend knows what to re-run
    trace = trace_from_langgraph(
        app, inputs,
        node_prompts={"planner": "plan.v1", "answerer": "answer.v1"},
        node_models={"planner": "gpt-4o", "answerer": "gpt-4o"},
        prompts={"plan.v1": "Plan how to answer.", "answer.v1": "Answer using the plan."},
    )
    # -> ingest with store.workflow_from_dict(trace) or dump to JSON for the CLI

How it works: the compiled graph's nodes/edges give the declared dependency DAG,
and `app.stream(input, stream_mode="updates")` yields each node's output as it
runs, so inputs/outputs/fingerprints are captured automatically.

Why per-node ids matter: recompute looks a node's `prompt_id` up in the trace's
`prompts` map to rebuild what to run. If every node shares one id with no text
(the bare-minimum default), only the *intervened* node can be recomputed from a
supplied prompt — recomputing *downstream* nodes has no prompt to use. Pass
`node_prompts` + `prompts` (and `node_models`) so the affected subgraph is
recompute-READY.

SCOPE (what this does and does NOT do):
- It captures metadata (graph, per-node ids, prompts, fingerprints) so the trace
  ingests and a change can be *gated*. It does NOT guarantee that recomputation
  reproduces the original node's execution.
- A captured node's recorded output is whatever the node actually produced; the
  recompute backend (e.g. Ollama) re-runs an LLM from the prompt + predecessor
  outputs. If the original node was not that same LLM call (a Python function, a
  tool call, hidden state), the recomputed output will differ for reasons that
  are NOT a model/prompt regression. Point this at genuinely LLM-backed nodes.
- ENTRY nodes (no declared predecessor) do not carry their initial LangGraph
  inputs in the fingerprint or `current_outputs`, and backends treat them as
  sources (echo the recorded output). So an intervention on the FIRST node is
  not faithfully recomputed yet — target a downstream node, or use the explicit
  `InstrumentedAgent` seam. Capturing initial inputs as source dependencies is
  future work.

HONEST CAVEAT (soundness): LangGraph nodes read a SHARED state object, so a
node's true inputs can include state written by non-adjacent nodes. Using the
graph's control-flow edges as the declared dependency edges therefore
UNDER-declares data dependencies — the classic missing-edge risk. This capture's
declared dependencies are UNVERIFIED (the trace carries
`dependency_coverage="unverified"`); `reuse_exposure` and the benchmark measure
the GENERAL risk, not whether THIS workflow's dependencies are complete. For
sound reuse, add the missing edges or use the explicit `InstrumentedAgent` seam.
v1 supports DAG graphs only (a node revisited in a loop is rejected)."""

from __future__ import annotations

import json
import warnings

from replaygate.replay.validity import fingerprint

_SPECIAL = {"__start__", "__end__"}

_MISSING_EDGE_WARNING = (
    "replaygate: LangGraph control-flow edges may under-declare true data "
    "dependencies (nodes share one state object), so THIS capture's declared "
    "dependencies are unverified (dependency_coverage='unverified'). reuse_exposure "
    "and the benchmark measure the general risk, not this workflow's completeness. "
    "For sound reuse, add the missing edges or use the explicit InstrumentedAgent seam."
)


def trace_from_langgraph(app, inputs, workflow_id: str = "langgraph",
                         model_id: str = "node", prompt_id: str = "default",
                         node_models: dict | None = None,
                         node_prompts: dict | None = None,
                         prompts: dict | None = None,
                         warn: bool = True) -> dict:
    """Run a compiled LangGraph `app` over each input and return a ReplayGate
    trace dict (contract: trace-input.md). `inputs` is a list of initial states.

    Per-node identity (so interventions can target one node and recompute works):
      - node_models: {node: model_id}  (falls back to `model_id`)
      - node_prompts: {node: prompt_id} (falls back to `prompt_id`)
      - prompts:      {prompt_id: prompt_text} -> the trace's prompts map, which the
                      recompute backend reads to rebuild each node's prompt.
    `warn=False` silences the missing-edge capture warning.
    """
    node_models = node_models or {}
    node_prompts = node_prompts or {}

    drawable = app.get_graph()
    real = [n for n in drawable.nodes if n not in _SPECIAL]
    edges = [(e.source, e.target) for e in drawable.edges
             if e.source in real and e.target in real]
    preds = {n: [s for s, t in edges if t == n] for n in real}

    if warn and any(preds[n] for n in real):
        warnings.warn(_MISSING_EDGE_WARNING, stacklevel=2)

    trajectories = []
    for i, inp in enumerate(inputs):
        outputs: dict[str, str] = {}
        steps: list[dict] = []
        for chunk in app.stream(inp, stream_mode="updates"):
            for node, update in chunk.items():
                if node not in real:
                    continue
                nm = node_models.get(node, model_id)
                npid = node_prompts.get(node, prompt_id)
                out = json.dumps(update, default=str, sort_keys=True)
                p = {d: outputs[d] for d in preds[node] if d in outputs}
                steps.append({
                    "step_index": len(steps), "node_name": node,
                    "input_fingerprint": fingerprint(node, nm, npid, p),
                    "output": out, "model_id": nm, "prompt_id": npid,
                    "cost": {"tokens": max(1, len(out) // 4), "latency_ms": 0.0},
                })
                outputs[node] = out
        trajectories.append({"trajectory_id": f"{workflow_id}-t{i}", "steps": steps})

    return {
        "workflow_id": workflow_id,
        "graph": {"nodes": real, "edges": [list(e) for e in edges]},
        "prompts": dict(prompts or {}),
        # Declared deps come from control-flow edges only; completeness is not proven
        # for this workflow (shared-state reads may be undeclared). See module docstring.
        "dependency_coverage": "unverified",
        "trajectories": trajectories,
    }
