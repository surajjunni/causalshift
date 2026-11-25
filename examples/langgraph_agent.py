"""LangGraph capture + recompute-wiring demo (NOT faithful end-to-end replay).

    pip install "replaygate[langgraph]"   # or: uv pip install langgraph
    python examples/langgraph_agent.py     # writes the trace + an intervention

Then gate the change on the capture (recompute needs a backend; Ollama shown):

    replaygate ingest examples/langgraph_trace.json
    replaygate diff --workflow lg_faq \\
        --intervention examples/langgraph_bad_prompt.json \\
        --backend ollama --evaluator judge

What this shows: the capture → ingest → gate PATH, and that per-node prompt ids +
prompt texts make a captured node recompute-ready.

What this is NOT: a faithful LLM replay. The nodes here are pure-Python, so an LLM
recompute backend would produce differently-shaped output for reasons that are not
a model/prompt regression — point ReplayGate at genuinely LLM-backed nodes for a
real verdict. The intervention targets a DOWNSTREAM node (`answerer`, which reads
`planner`'s captured output): an intervention on the ENTRY node is not faithfully
recomputed yet, because initial LangGraph inputs are not captured as dependencies
(see the adapter docstring).
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
    plan: str
    answer: str


def main() -> int:
    g = StateGraph(State)
    g.add_node("planner", lambda s: {"plan": f"plan({s['question']})"})
    g.add_node("answerer", lambda s: {"answer": f"answer<{s['plan']}>"})
    g.add_edge(START, "planner")
    g.add_edge("planner", "answerer")
    g.add_edge("answerer", END)
    app = g.compile()

    # Give each node its real prompt id + text, so recompute can rebuild them.
    node_prompts = {"planner": "plan.v1", "answerer": "answer.v1"}
    node_models = {"planner": "llama3", "answerer": "llama3"}
    prompts = {
        "plan.v1": "Make a short plan to answer the question.",
        "answer.v1": "Answer the question using the plan.",
    }

    questions = ["what is x?", "how does y work?", "why z?", "define w"]
    trace = trace_from_langgraph(
        app, inputs=[{"question": q} for q in questions], workflow_id="lg_faq",
        node_prompts=node_prompts, node_models=node_models, prompts=prompts,
    )
    trace_path = _ROOT / "examples" / "langgraph_trace.json"
    trace_path.write_text(json.dumps(trace, indent=2))

    # A prompt-change intervention targeting ONE node (the answerer).
    intervention = {
        "workflow_id": "lg_faq",
        "targets": {"answerer": {"prompt_id": "answer.v2"}},
        "prompts": {"answer.v2": "Answer in a single vague word, nothing else."},
    }
    interv_path = _ROOT / "examples" / "langgraph_bad_prompt.json"
    interv_path.write_text(json.dumps(intervention, indent=2))

    print(f"captured {len(trace['trajectories'])} trajectories from LangGraph → {trace_path}")
    print(f"  nodes:    {trace['graph']['nodes']}")
    print(f"  edges:    {trace['graph']['edges']}")
    print(f"  prompts:  {[s['prompt_id'] for s in trace['trajectories'][0]['steps']]}")
    print(f"  wrote prompt-change intervention → {interv_path}")
    print(f"  dependency_coverage: {trace['dependency_coverage']} "
          "(control-flow edges only; not proven complete)")
    print("\nnext — gate the change on the capture:")
    print("  replaygate ingest examples/langgraph_trace.json")
    print("  replaygate diff --workflow lg_faq "
          "--intervention examples/langgraph_bad_prompt.json "
          "--backend ollama --evaluator judge")
    print("\nnote: pure-Python nodes here — this demonstrates the path, not a faithful")
    print("      LLM replay. Use real LLM-backed nodes and target a downstream node.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
