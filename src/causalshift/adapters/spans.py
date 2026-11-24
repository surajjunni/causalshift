"""Generic span → CausalShift trace core.

Most tracing stacks (OpenTelemetry / OpenInference, MLflow Tracing, the OpenAI
Agents SDK, LlamaIndex instrumentation) expose a run as spans with a name, a
parent, and an output. This converts any such span stream into a CausalShift
trace: span name → node, parent→child → declared dependency edge, output →
recorded output, with fingerprints the replay validity predicate consumes.

A "span" here is a dict or object exposing:
  - name   : str          (the node/step name)
  - parent : str | None   (the PARENT NODE NAME, or None for a root)
  - output : str | Any    (serialized if not a str)

`traces` is a list of trajectories; each trajectory is a list of spans in
execution order. Framework shims (mlflow.py, …) normalize to this shape.

Soundness caveat (same as all adapters): the parent/child span tree is a
CONTROL-FLOW structure. If a step truly reads data a non-parent span produced,
these edges under-declare the dependency (the missing-edge risk) — which
`reuse_exposure` and the benchmark measure, never hide. Add edges or use the
explicit seam where a step has hidden cross-span reads. DAG-only."""

from __future__ import annotations

import json

from causalshift.replay.validity import fingerprint


def _attr(span, key):
    return span.get(key) if isinstance(span, dict) else getattr(span, key, None)


def _as_str(v) -> str:
    return v if isinstance(v, str) else json.dumps(v, default=str, sort_keys=True)


def trace_from_spans(traces, workflow_id: str = "spans", model_id: str = "span",
                     prompt_id: str = "default") -> dict:
    node_order: list[str] = []
    edge_set: set[tuple[str, str]] = set()
    trajectories = []

    for i, spans in enumerate(traces):
        outputs: dict[str, str] = {}
        steps: list[dict] = []
        for span in spans:
            name = _attr(span, "name")
            parent = _attr(span, "parent")
            out = _as_str(_attr(span, "output"))
            if name not in node_order:
                node_order.append(name)
            if parent:
                edge_set.add((parent, name))
            preds = {parent: outputs[parent]} if parent and parent in outputs else {}
            steps.append({
                "step_index": len(steps), "node_name": name,
                "input_fingerprint": fingerprint(name, model_id, prompt_id, preds),
                "output": out, "model_id": model_id, "prompt_id": prompt_id,
                "cost": {"tokens": max(1, len(out) // 4), "latency_ms": 0.0},
            })
            outputs[name] = out
        trajectories.append({"trajectory_id": f"{workflow_id}-t{i}", "steps": steps})

    return {
        "workflow_id": workflow_id,
        "graph": {"nodes": node_order, "edges": [list(e) for e in sorted(edge_set)]},
        "prompts": {},
        "trajectories": trajectories,
    }
