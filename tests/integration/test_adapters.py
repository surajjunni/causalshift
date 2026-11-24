"""Framework adapters produce valid, replayable traces (validated against each
framework's documented object shape, via constructed inputs — no heavy installs)."""

from types import SimpleNamespace

from replaygate.adapters.crewai import trace_from_crewai
from replaygate.adapters.mlflow import trace_from_mlflow
from replaygate.adapters.spans import trace_from_spans
from replaygate.graph.dag import DependencyGraph
from replaygate.replay.validity import reusable
from replaygate.store.db import workflow_from_dict


def _assert_reusable(trace):
    wf = workflow_from_dict(trace)                 # raises if invalid
    g = DependencyGraph(wf)
    t0 = wf.trajectories[0]
    outputs = t0.output_map()
    for s in t0.steps:
        ok, why = reusable(s.node_name, g, s.input_fingerprint, outputs,
                           s.model_id, s.prompt_id)
        assert ok, f"{s.node_name} not reusable: {why}"
    return wf


def test_generic_spans():
    traces = [[
        {"name": "planner", "parent": None, "output": "p1"},
        {"name": "answerer", "parent": "planner", "output": "a1"},
    ], [
        {"name": "planner", "parent": None, "output": "p2"},
        {"name": "answerer", "parent": "planner", "output": "a2"},
    ]]
    wf = _assert_reusable(trace_from_spans(traces, workflow_id="s"))
    assert wf.nodes == ["planner", "answerer"]
    assert wf.edges == [("planner", "answerer")]
    assert len(wf.trajectories) == 2


def test_mlflow_shim_resolves_parent_ids():
    spans = [
        SimpleNamespace(span_id="1", parent_id=None, name="retrieve", outputs={"docs": 3}),
        SimpleNamespace(span_id="2", parent_id="1", name="generate", outputs={"text": "ok"}),
    ]
    trace = SimpleNamespace(data=SimpleNamespace(spans=spans))
    wf = _assert_reusable(trace_from_mlflow(trace, workflow_id="mlf"))
    assert wf.edges == [("retrieve", "generate")]


def test_crewai_context_becomes_edges():
    research = SimpleNamespace(name="research", context=[])
    write = SimpleNamespace(name="write", context=[research])
    crew_out = SimpleNamespace(tasks_output=[
        SimpleNamespace(raw="findings"), SimpleNamespace(raw="article")])
    wf = _assert_reusable(trace_from_crewai([research, write], crew_out, workflow_id="cw"))
    assert wf.nodes == ["research", "write"]
    assert wf.edges == [("research", "write")]
