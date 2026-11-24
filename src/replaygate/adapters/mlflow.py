"""MLflow Tracing → ReplayGate trace (thin shim over the generic span core).

    import mlflow
    # ... run your agent under mlflow tracing ...
    traces = mlflow.search_traces(...)          # or a single trace object
    cs_trace = trace_from_mlflow(traces)

MLflow spans expose span_id / parent_id / name / outputs; we resolve
parent_id → parent node name and delegate to trace_from_spans. Works on MLflow
Trace objects (`.data.spans`) or already-extracted span lists. Validated against
MLflow's documented span shape — confirm against your MLflow version."""

from __future__ import annotations

from replaygate.adapters.spans import _attr, trace_from_spans


def _spans_of(trace):
    # MLflow Trace -> .data.spans; else assume it's already a list of spans
    data = _attr(trace, "data")
    if data is not None:
        spans = _attr(data, "spans")
        if spans is not None:
            return spans
    if isinstance(trace, (list, tuple)):
        return trace
    raise TypeError("expected an MLflow Trace (with .data.spans) or a list of spans")


def _normalize(trace):
    spans = _spans_of(trace)
    id2name = {_attr(s, "span_id"): _attr(s, "name") for s in spans}
    norm = []
    for s in spans:
        pid = _attr(s, "parent_id")
        norm.append({
            "name": _attr(s, "name"),
            "parent": id2name.get(pid) if pid else None,
            "output": _attr(s, "outputs"),
        })
    return norm


def trace_from_mlflow(traces, workflow_id: str = "mlflow", model_id: str = "span",
                      prompt_id: str = "default") -> dict:
    """Accept a single MLflow Trace or a list of them; return a ReplayGate trace."""
    many = traces if isinstance(traces, (list, tuple)) and traces and (
        _attr(traces[0], "data") is not None) else [traces]
    normalized = [_normalize(t) for t in many]
    return trace_from_spans(normalized, workflow_id=workflow_id,
                            model_id=model_id, prompt_id=prompt_id)
