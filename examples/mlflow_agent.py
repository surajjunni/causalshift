"""Capture a ReplayGate trace from MLflow Tracing.

Runs with NO mlflow install: it uses stand-in span objects that mirror MLflow's
real span shape (span_id / parent_id / name / outputs) so you can see the adapter
end to end. With real MLflow, delete the stand-ins and use the commented call.

    python examples/mlflow_agent.py     # -> examples/mlflow_trace.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent.parent
for p in (str(_ROOT), str(_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from replaygate.adapters.mlflow import trace_from_mlflow  # noqa: E402


def _span(span_id, parent_id, name, outputs):
    # mirrors an mlflow.entities.Span (the fields the adapter reads)
    return SimpleNamespace(span_id=span_id, parent_id=parent_id, name=name, outputs=outputs)


def _fake_trace(question):
    # one MLflow Trace == one trajectory: .data.spans
    spans = [
        _span("1", None, "retrieve", {"docs": f"docs_for({question})"}),
        _span("2", "1", "rerank", {"top": "doc#2"}),
        _span("3", "2", "generate", {"answer": f"answer({question})"}),
    ]
    return SimpleNamespace(data=SimpleNamespace(spans=spans))


def main() -> int:
    # --- with real MLflow, replace the stand-ins below with: ---
    #   import mlflow
    #   traces = mlflow.search_traces(experiment_ids=[...], return_type="list")
    traces = [_fake_trace(q) for q in ("what is x?", "why y?", "how z?")]

    trace = trace_from_mlflow(traces, workflow_id="mlflow_rag")
    out = _ROOT / "examples" / "mlflow_trace.json"
    out.write_text(json.dumps(trace, indent=2))
    print(f"captured {len(trace['trajectories'])} trajectories from MLflow spans → {out}")
    print(f"  nodes: {trace['graph']['nodes']}")
    print(f"  edges: {trace['graph']['edges']}   (span parent/child → dependency edges)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
