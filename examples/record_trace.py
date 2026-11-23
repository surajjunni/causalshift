"""Record a REAL text trace by running a small 3-step agent on live Ollama.

Agent DAG:  question → planner → retriever → responder   (terminal = responder)

Writes examples/real_trace.json (trace-input contract, incl. the prompt
registry) and examples/bad_prompt.json (a candidate intervention that swaps the
responder's prompt for a deliberately vague one). Then:

    causalshift ingest examples/real_trace.json --db /tmp/cs_real.db
    causalshift evaluate --workflow real --intervention examples/bad_prompt.json \\
        --db /tmp/cs_real.db --backend ollama --evaluator judge --mode selective
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for p in (str(_ROOT), str(_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from causalshift.backends.base import Produced          # noqa: E402
from causalshift.backends.ollama import OllamaBackend, ollama_available  # noqa: E402
from causalshift.replay.validity import fingerprint     # noqa: E402

MODEL = "llama3:latest"
NODES = ["question", "planner", "retriever", "responder"]
EDGES = [("question", "planner"), ("planner", "retriever"), ("retriever", "responder")]
PREDS = {"question": [], "planner": ["question"], "retriever": ["planner"],
         "responder": ["retriever"]}
PROMPT_ID = {"question": "verbatim", "planner": "plan.v1",
             "retriever": "retrieve.v1", "responder": "respond.v1"}
MODEL_ID = {"question": "source", "planner": MODEL, "retriever": MODEL, "responder": MODEL}

PROMPTS = {
    "verbatim": "(external input)",
    "plan.v1": "You are a planner. In ONE sentence, outline how to answer the user's question.",
    "retrieve.v1": "You are a knowledge step. Given the plan, list 2-3 concise factual "
                   "bullet points needed to answer.",
    "respond.v1": "You are the responder. Using the facts, write a clear, correct 2-3 "
                  "sentence answer.",
    "respond.bad": "You are the responder. Reply with a single vague word, nothing else.",
}

QUESTIONS = [
    "What is the capital of France and why is it significant?",
    "How does a bicycle stay upright while moving?",
    "What causes the seasons on Earth?",
    "Why is the sky blue during the day?",
    "What is photosynthesis in simple terms?",
]


def main() -> int:
    if not ollama_available():
        print("Ollama not reachable at localhost:11434 — start it, then re-run.", file=sys.stderr)
        return 2
    backend = OllamaBackend(model=MODEL, prompts=PROMPTS, num_predict=96)

    trajectories = []
    for i, q in enumerate(QUESTIONS):
        current = {"question": q}
        steps = []
        for node in NODES:
            if node == "question":
                out = q
            else:
                res = backend.recompute(node, MODEL_ID[node], PROMPT_ID[node],
                                        current, PREDS[node])
                out = res.output if isinstance(res, Produced) else "(unavailable)"
            current[node] = out
            preds = {p: current[p] for p in PREDS[node]}
            steps.append({
                "step_index": NODES.index(node), "node_name": node,
                "input_fingerprint": fingerprint(node, MODEL_ID[node], PROMPT_ID[node], preds),
                "output": out, "model_id": MODEL_ID[node], "prompt_id": PROMPT_ID[node],
                "cost": {"tokens": 96, "latency_ms": 0.0},
            })
        trajectories.append({"trajectory_id": f"real-t{i}", "steps": steps})
        print(f"  recorded t{i}: {q[:40]}… → {current['responder'][:50]!r}")

    trace = {"workflow_id": "real",
             "graph": {"nodes": NODES, "edges": [list(e) for e in EDGES]},
             "prompts": PROMPTS, "trajectories": trajectories}
    out_dir = _ROOT / "examples"
    (out_dir / "real_trace.json").write_text(json.dumps(trace, indent=2))
    (out_dir / "bad_prompt.json").write_text(json.dumps(
        {"workflow_id": "real", "targets": {"responder": {"prompt_id": "respond.bad"}},
         "prompts": {"respond.bad": PROMPTS["respond.bad"]}}, indent=2))
    print(f"\nwrote {out_dir/'real_trace.json'} ({len(trajectories)} trajectories) "
          f"and {out_dir/'bad_prompt.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
