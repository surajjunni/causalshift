"""The instrumentation seam produces a valid, replayable trace, and its
fingerprints are the ones the validity predicate consumes (so reuse works)."""

from replaygate.graph.dag import DependencyGraph
from replaygate.instrument import InstrumentedAgent
from replaygate.replay.validity import reusable
from replaygate.store.db import TraceStore, workflow_from_dict


def _agent():
    agent = InstrumentedAgent("demo")

    @agent.node("double", deps=["question"], model_id="m1", prompt_id="p.double")
    def double(question):
        return float(question) * 2

    @agent.node("answer", deps=["double"], model_id="m1", prompt_id="p.answer")
    def answer(double):
        return float(double) + 1

    for i, q in enumerate([1.0, 2.0, 3.0]):
        with agent.trajectory(f"t{i}") as run:
            run.set("question", q)
            run.run_all()
    return agent


def test_trace_validates_and_has_expected_shape():
    td = _agent().to_trace_dict()
    wf = workflow_from_dict(td)                 # raises TraceInputError if invalid
    assert wf.nodes == ["question", "double", "answer"]
    assert wf.edges == [("question", "double"), ("double", "answer")]
    assert len(wf.trajectories) == 3
    for t in wf.trajectories:
        for s in t.steps:
            assert s.input_fingerprint   # every step carries a fingerprint


def test_roundtrips_through_store():
    wf = workflow_from_dict(_agent().to_trace_dict())
    store = TraceStore(":memory:")
    store.ingest(wf)
    hy = store.hydrate("demo")
    assert hy.nodes == wf.nodes and hy.edges == wf.edges
    assert len(hy.trajectories) == len(wf.trajectories)


def test_fingerprints_are_reusable_by_the_validity_predicate():
    wf = workflow_from_dict(_agent().to_trace_dict())
    g = DependencyGraph(wf)
    t0 = wf.trajectories[0]
    outputs = t0.output_map()
    fp = {s.node_name: s.input_fingerprint for s in t0.steps}
    mp = {s.node_name: (s.model_id, s.prompt_id) for s in t0.steps}
    # with inputs unchanged, every non-source node must be judged reusable
    for node in ("double", "answer"):
        ok, why = reusable(node, g, fp[node], outputs, *mp[node])
        assert ok, f"{node} should be reusable but was not: {why}"
