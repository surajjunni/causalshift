"""End-to-end LIVE demo: instrument a real Ollama agent with the InstrumentedAgent
seam, record a trace, then evaluate a prompt change on it — one script.

    python examples/live_agent.py            # record only → examples/real_trace.json
    python examples/live_agent.py --evaluate # also run selective vs full verdicts

Recording and replay share the SAME OllamaBackend prompt-construction, so the
recorded baseline and the recomputed candidate are directly comparable. Needs a
local Ollama (llama3). The seam is the only instrumentation: declare deps once.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for p in (str(_ROOT), str(_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from causalshift.backends.base import Produced                    # noqa: E402
from causalshift.backends.ollama import OllamaBackend, ollama_available  # noqa: E402
from causalshift.instrument import InstrumentedAgent              # noqa: E402

MODEL = "llama3:latest"
REG = {
    "plan.v1": "You are a planner. In ONE sentence, outline how to answer the question.",
    "retrieve.v1": "You are a knowledge step. List 2-3 concise factual bullets needed to answer.",
    "respond.v1": "You are the responder. Using the facts, write a clear, correct 2-3 "
                  "sentence answer.",
    "respond.bad": "You are the responder. Reply with a single vague word, nothing else.",
}
QUESTIONS = [
    "What is the capital of France and why is it significant?",
    "How does a bicycle stay upright while moving?",
    "What causes the seasons on Earth?",
    "Why is the sky blue during the day?",
]


def _llm_node(agent, backend, name, deps, prompt_id):
    @agent.node(name, deps=deps, model_id=MODEL, prompt_id=prompt_id, prompt=REG[prompt_id])
    def _fn(**kw):
        res = backend.recompute(name, MODEL, prompt_id, dict(kw), list(deps))
        if isinstance(res, Produced):
            return res.output
        raise RuntimeError(f"recording failed at {name}: {res.reason}")
    return _fn


def record(agent, rec_backend):
    _llm_node(agent, rec_backend, "planner", ["question"], "plan.v1")
    _llm_node(agent, rec_backend, "retriever", ["planner"], "retrieve.v1")
    _llm_node(agent, rec_backend, "responder", ["retriever"], "respond.v1")
    for i, q in enumerate(QUESTIONS):
        with agent.trajectory(f"real-t{i}") as run:
            run.set("question", q)
            run.run_all()
        print(f"  recorded t{i}: {q[:38]}…")


def evaluate(agent):
    from causalshift.evaluate.judge import OllamaJudge
    from causalshift.graph.dag import DependencyGraph
    from causalshift.models import Intervention
    from causalshift.replay.engine import full_replay, selective_replay
    from causalshift.report.verdict import build_verdict, format_verdict

    wf = __import__("causalshift.store.db", fromlist=["workflow_from_dict"]) \
        .workflow_from_dict(agent.to_trace_dict())
    graph = DependencyGraph(wf)
    intervention = Intervention("real", {"responder": {"prompt_id": "respond.bad"}})
    judge = OllamaJudge(model=MODEL, target="responder")

    for mode, fn in [("selective", selective_replay), ("full", full_replay)]:
        backend = OllamaBackend(prompts=REG, num_predict=96)
        results = [fn(t, graph, intervention, backend, judge) for t in wf.trajectories]
        v = build_verdict("real", mode, results)
        print(f"\n### {mode.upper()} — recompute calls: {backend.calls}")
        print(format_verdict(v))


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not ollama_available():
        print("Ollama not reachable at localhost:11434 — start it, then re-run.", file=sys.stderr)
        return 2
    agent = InstrumentedAgent("real")
    record(agent, OllamaBackend(prompts=REG, num_predict=96))
    agent.save(str(_ROOT / "examples" / "real_trace.json"))
    import json
    (_ROOT / "examples" / "bad_prompt.json").write_text(json.dumps(
        {"workflow_id": "real", "targets": {"responder": {"prompt_id": "respond.bad"}},
         "prompts": {"respond.bad": REG["respond.bad"]}}, indent=2))
    print(f"wrote examples/real_trace.json ({len(QUESTIONS)} trajectories) via the seam")
    if "--evaluate" in argv:
        evaluate(agent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
