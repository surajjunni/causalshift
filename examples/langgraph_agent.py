"""Capture a ReplayGate trace from a LangGraph app with ~2 lines of glue.

    pip install "replaygate[langgraph]"   # or: uv pip install langgraph
    python examples/langgraph_agent.py     # -> examples/langgraph_trace.json

Pure-Python nodes (no LLM) so it runs anywhere and shows the capture path.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TypedDict

_ROOT = Path(__file__).resolve().parent.parent
for p in (str(_ROOT), str(_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from langgraph.graph import START, END, StateGraph
except ImportError:
    print("install langgraph first:  uv pip install langgraph", file=sys.stderr)
    raise SystemExit(2)

from replaygate.adapters.langgraph import trace_from_langgraph  # noqa: E402


class State(TypedDict):
    question: str
    topic: str
    facts: str
    answer: str


def main() -> int:
    g = StateGraph(State)
    g.add_node("classify", lambda s: {"topic": f"topic:{len(s['question']) % 3}"})
    g.add_node("retrieve", lambda s: {"facts": f"facts_for_{s['topic']}"})
    g.add_node("answer", lambda s: {"answer": f"answer<{s['facts']}>"})
    g.add_edge(START, "classify")
    g.add_edge("classify", "retrieve")
    g.add_edge("retrieve", "answer")
    g.add_edge("answer", END)
    app = g.compile()

    questions = ["what is x?", "how does y work?", "why z?", "define w"]
    trace = trace_from_langgraph(app, inputs=[{"question": q} for q in questions],
                                 workflow_id="lg_faq")
    out = _ROOT / "examples" / "langgraph_trace.json"
    out.write_text(json.dumps(trace, indent=2))
    print(f"captured {len(trace['trajectories'])} trajectories from LangGraph → {out}")
    print(f"  nodes: {trace['graph']['nodes']}")
    print(f"  edges: {trace['graph']['edges']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
