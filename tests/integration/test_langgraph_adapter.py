"""The LangGraph adapter captures a valid, replayable ReplayGate trace."""

import pytest

pytest.importorskip("langgraph")

from typing import TypedDict  # noqa: E402

from langgraph.graph import START, END, StateGraph  # noqa: E402

from replaygate.adapters.langgraph import trace_from_langgraph  # noqa: E402
from replaygate.graph.dag import DependencyGraph  # noqa: E402
from replaygate.replay.validity import reusable  # noqa: E402
from replaygate.store.db import TraceStore, workflow_from_dict  # noqa: E402


class _S(TypedDict):
    q: str
    plan: str
    answer: str


def _app():
    g = StateGraph(_S)
    g.add_node("planner", lambda s: {"plan": f"plan({s['q']})"})
    g.add_node("answerer", lambda s: {"answer": f"ans({s['plan']})"})
    g.add_edge(START, "planner")
    g.add_edge("planner", "answerer")
    g.add_edge("answerer", END)
    return g.compile()


def _trace():
    return trace_from_langgraph(_app(), inputs=[{"q": "a"}, {"q": "bb"}, {"q": "ccc"}],
                                workflow_id="lg")


def test_captured_trace_validates_and_shape():
    wf = workflow_from_dict(_trace())              # raises if invalid
    assert set(wf.nodes) == {"planner", "answerer"}
    assert wf.edges == [("planner", "answerer")]
    assert len(wf.trajectories) == 3
    for t in wf.trajectories:
        assert [s.node_name for s in t.steps] == ["planner", "answerer"]
        assert all(s.input_fingerprint for s in t.steps)


def test_roundtrips_and_fingerprints_are_reusable():
    wf = workflow_from_dict(_trace())
    TraceStore(":memory:").ingest(wf)              # store accepts it
    g = DependencyGraph(wf)
    t0 = wf.trajectories[0]
    outputs = t0.output_map()
    for s in t0.steps:
        ok, why = reusable(s.node_name, g, s.input_fingerprint, outputs,
                           s.model_id, s.prompt_id)
        assert ok, f"{s.node_name} should be reusable: {why}"
