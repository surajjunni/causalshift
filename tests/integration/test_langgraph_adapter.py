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


def test_per_node_prompt_and_model_ids_and_prompts_map():
    trace = trace_from_langgraph(
        _app(), inputs=[{"q": "a"}], workflow_id="lg", warn=False,
        node_prompts={"planner": "plan.v1", "answerer": "ans.v1"},
        node_models={"planner": "m1", "answerer": "m2"},
        prompts={"plan.v1": "Plan.", "ans.v1": "Answer."})
    assert trace["prompts"] == {"plan.v1": "Plan.", "ans.v1": "Answer."}
    steps = {s["node_name"]: s for s in trace["trajectories"][0]["steps"]}
    assert steps["planner"]["prompt_id"] == "plan.v1" and steps["planner"]["model_id"] == "m1"
    assert steps["answerer"]["prompt_id"] == "ans.v1" and steps["answerer"]["model_id"] == "m2"


def test_missing_edge_warning_is_emitted():
    import warnings
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        trace_from_langgraph(_app(), inputs=[{"q": "a"}], workflow_id="lg")
    assert any("unverified" in str(w.message) for w in caught)


def test_trace_marks_dependency_coverage_unverified():
    # declared deps come from control-flow edges only; the capture must not imply they
    # are proven complete for this workflow.
    trace = trace_from_langgraph(_app(), inputs=[{"q": "a"}], workflow_id="lg", warn=False)
    assert trace["dependency_coverage"] == "unverified"


def test_dependency_coverage_survives_ingest_and_hydrate():
    # the annotation must reach the gate, not vanish at ingest (review follow-up).
    trace = trace_from_langgraph(_app(), inputs=[{"q": "a"}], workflow_id="lg", warn=False)
    store = TraceStore(":memory:")
    store.ingest(workflow_from_dict(trace))
    assert store.hydrate("lg").dependency_coverage == "unverified"


def test_absent_coverage_defaults_to_declared():
    raw = {"workflow_id": "w", "graph": {"nodes": ["a"], "edges": []},
           "trajectories": [{"trajectory_id": "t", "steps": [
               {"step_index": 0, "node_name": "a", "input_fingerprint": "f", "output": "o"}]}]}
    wf = workflow_from_dict(raw)
    assert wf.dependency_coverage == "declared"
    store = TraceStore(":memory:")
    store.ingest(wf)
    assert store.hydrate("w").dependency_coverage == "declared"


def test_unverified_capture_blocks_a_passing_selective_verdict():
    # End-to-end (review): ingest a LangGraph 'unverified' capture, run an otherwise-passing
    # selective evaluation, and confirm the gate downgrades PASS -> INCONCLUSIVE (exit 2).
    from replaygate.models import Intervention
    from replaygate.replay.engine import selective_replay
    from replaygate.backends.base import UnavailableBackend
    from replaygate.evaluate.quality import TerminalSignalEvaluator
    from replaygate.report.verdict import (
        build_verdict, gate_unverified_dependencies, verdict_exit_code,
    )

    trace = trace_from_langgraph(
        _app(), inputs=[{"q": "a"}, {"q": "bb"}, {"q": "ccc"}, {"q": "dddd"}],
        workflow_id="lg", warn=False)
    store = TraceStore(":memory:")
    store.ingest(workflow_from_dict(trace))
    wf = store.hydrate("lg")
    assert wf.dependency_coverage == "unverified"

    g = DependencyGraph(wf)
    noop = Intervention(workflow_id="lg", targets={})   # change nothing -> reuse all, delta 0
    evaluator = TerminalSignalEvaluator(target="answerer")
    results = [selective_replay(t, g, noop, UnavailableBackend(), evaluator)
               for t in wf.trajectories]
    verdict = build_verdict("lg", "selective", results)
    assert verdict.status == "PASS"                     # otherwise safe

    downgraded = gate_unverified_dependencies(verdict, wf.dependency_coverage)
    assert downgraded is True
    assert verdict.status == "INCONCLUSIVE"
    assert verdict_exit_code(verdict) == 2
