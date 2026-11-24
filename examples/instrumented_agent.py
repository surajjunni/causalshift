"""Instrument a real (here, pure-Python, deterministic) agent with the
InstrumentedAgent seam and emit a CausalShift trace — no LLM needed, so it runs
anywhere and shows exactly what instrumentation a user must add: declare each
node's deps once; inputs/outputs/fingerprints are captured automatically.

    python examples/instrumented_agent.py
    causalshift ingest examples/instrumented_trace.json --db /tmp/cs_instr.db
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for p in (str(_ROOT), str(_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from causalshift.instrument import InstrumentedAgent  # noqa: E402

agent = InstrumentedAgent("faq")


@agent.node("classify", deps=["question"], model_id="router.v1", prompt_id="classify.v1",
            prompt="Classify the question into a topic id.")
def classify(question):
    return f"topic:{len(question) % 3}"


@agent.node("retrieve", deps=["classify"], model_id="kb.v1", prompt_id="retrieve.v1",
            prompt="Return facts for the classified topic.")
def retrieve(classify):
    return f"facts_for_{classify}"


@agent.node("answer", deps=["retrieve"], model_id="writer.v1", prompt_id="answer.v1",
            prompt="Write the answer using the retrieved facts.")
def answer(retrieve):
    return f"answer<{retrieve}>"


def main() -> int:
    questions = ["what is x?", "how does y work?", "why z?", "define w", "explain q"]
    for i, q in enumerate(questions):
        with agent.trajectory(f"faq-t{i}") as run:
            run.set("question", q)
            run.run_all()
    out = agent.save(str(_ROOT / "examples" / "instrumented_trace.json"))
    td = agent.to_trace_dict()
    print(f"wrote {out}")
    print(f"  nodes: {td['graph']['nodes']}")
    print(f"  edges: {td['graph']['edges']}")
    print(f"  trajectories: {len(td['trajectories'])}, prompts: {list(td['prompts'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
