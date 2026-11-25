# ReplayGate

[![CI](https://github.com/surajjunni/replaygate/actions/workflows/ci.yml/badge.svg)](https://github.com/surajjunni/replaygate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)

**Did your prompt or model change make your AI agent worse? Find out before you ship it.**

You tweak a prompt, or swap one model for another. Your tests pass. But a multi-step
agent is hard to test, and the change might quietly make 1 in 5 answers worse. ReplayGate
checks that against your **real past runs**, not hand-written test cases, and gives you a
clear go / no-go answer.

📝 **Launch post:** [Your agent's prompt change passed CI. Did it actually get *worse*?](https://surajjyothiunni1.substack.com/p/your-agents-prompt-change-passed)

## What it does

When you change a prompt or model behind an agent, ReplayGate:

1. **Replays your real recorded runs** under the change.
2. **Re-runs only the steps the change can affect**, and reuses the rest. That keeps it cheap.
3. **Gives a clear verdict:** PASS, FAIL, or INCONCLUSIVE. When it can't tell, it blocks the
   deploy instead of guessing.

It drops into CI through exit codes: `0` = safe, `1` = regressed, `2` = can't tell (also blocks).

## Install

```bash
uv venv && uv pip install -e ".[dev]"   # or: pip install -e ".[dev]"
```

## Quick start

One command answers "is this change safe?":

```bash
replaygate ingest trajectories.json
replaygate diff --workflow W --intervention change.json --backend ollama --evaluator judge
```

You get a plain-language report:

```text
ReplayGate — change risk report [W]

  ✗ FAIL — quality regresses
  → Don't ship: quality regresses — the 95% CI is entirely past the margin.

  change:       responder
  impact:       -0.675 mean quality (95% CI [-0.850, -0.500], margin -0.000) — candidate scores 0.675 lower on average
  cost:         selective made 4 model call(s); full re-execution ≈ 12 (saved ~8, 67%)
  reuse:        exposure 0.75 — fraction of nodes reused, not a miss probability
  exit:         1  (0 PASS / 1 FAIL / 2 INCONCLUSIVE)
```

Useful flags: `--margin` (how much quality drop you'll tolerate before FAIL), `--format markdown`
(paste the report into a pull request), and `--json` (for scripts).

**Where to run the change.** `--backend` picks what re-runs the affected steps: `ollama` (local),
`openai`, or `anthropic`. Cloud backends read the key from your environment (`OPENAI_API_KEY` /
`ANTHROPIC_API_KEY`); the key is never put on the command line or logged. If a key is missing or an
API call fails, those steps are marked INCONCLUSIVE and the run exits `2`. It never calls that a pass.

```bash
export OPENAI_API_KEY=...   # in your shell, not in ReplayGate
replaygate diff --workflow W --intervention change.json --backend openai --evaluator judge
```

## Record your agent's runs

ReplayGate needs a recording of your agent's past runs. The one thing you add is: say what each
step depends on, once. Inputs, outputs, and fingerprints are captured for you.

```python
from replaygate.instrument import InstrumentedAgent

agent = InstrumentedAgent("support")

@agent.node("planner", deps=["question"], prompt_id="plan.v1", prompt="Plan how to answer.")
def planner(question): ...

@agent.node("responder", deps=["planner"], prompt_id="respond.v1", prompt="Answer using the plan.")
def responder(planner): ...

for i, q in enumerate(questions):
    with agent.trajectory(f"t{i}") as run:
        run.set("question", q)   # a starting input
        run.run_all()            # runs the steps in order and records each one

agent.save("trace.json")         # ready for `replaygate ingest`
```

**Already using LangGraph?** Capture a trace from a compiled graph with almost no code:

```python
from replaygate.adapters.langgraph import trace_from_langgraph

app = graph.compile()
trace = trace_from_langgraph(app, inputs=[{"q": q} for q in questions])
# -> dump to JSON for `replaygate ingest`
```

One caveat for LangGraph: its steps share one state object, so the graph's edges can miss some real
dependencies. ReplayGate marks such a capture `dependency_coverage="unverified"` and shows that on the
report, so you know reuse might be optimistic. For steps with hidden reads, add the missing edges or
use the explicit setup above. See `examples/langgraph_agent.py`.

## Works with

| Framework | How to capture | Example |
|---|---|---|
| **LangGraph** | `adapters.langgraph.trace_from_langgraph(app, inputs)` | `examples/langgraph_agent.py` |
| **MLflow Tracing** | `adapters.mlflow.trace_from_mlflow(traces)` | `examples/mlflow_agent.py` |
| **CrewAI** | `adapters.crewai.trace_from_crewai(tasks, crew.kickoff())` | `examples/crewai_agent.py` |
| **OpenAI Agents SDK / LlamaIndex / OpenTelemetry** | normalize spans to `{name, parent, output}` and call `adapters.spans.trace_from_spans(traces)` | span recipe below |

Every example runs with **no framework install** (stand-ins mirror the real shape), so you can see
the capture path first, then swap in your real app.

```python
from replaygate.adapters.spans import trace_from_spans
# each run is a list of spans; a span is {"name", "parent": <parent name or None>, "output"}
trace = trace_from_spans([[{"name": "retrieve", "parent": None, "output": docs},
                           {"name": "answer", "parent": "retrieve", "output": ans}]])
```

## When it isn't sure, it says so

ReplayGate is cheap because it reuses old results for steps the change can't touch. That is only
safe if it knows the real dependencies between steps. If a dependency is missing, it could reuse a
stale result and **miss a real regression**.

ReplayGate does not hide this:

- It **measures how often it misses** (the false-negative rate) on a test set with known answers:
  `replaygate benchmark`.
- When it can't prove a step is safe to reuse, it **re-runs the step** instead of guessing.
- You can always force a full re-run with `--mode full`, which is slower but always correct.

```bash
replaygate benchmark          # the quality gate: how often does reuse miss a regression?
python benchmark/sweep.py     # shows the miss rate grows with missing edges, not with the policy
```

## How it compares

- **Tracely and similar replay tools** replay recorded outputs to catch wiring bugs. They can't test
  a model or prompt *change*, because the recording is exactly what the change would alter.
  ReplayGate tests that change.
- **DeepEval / promptfoo** compare models and prompts, but on hand-written cases. ReplayGate uses
  your real recorded traffic.
- **Single-run failure attribution** tools explain why one run failed. ReplayGate answers a different
  question: is this change safe across many runs, and which step is responsible?

## Scope

v1 works with agents whose steps form a simple one-way flow (a DAG) and whose dependencies you have
declared. Loops and hidden-state agents are rejected, not silently guessed at. The governing
principles are in `.specify/memory/constitution.md`.

---

**Keywords:** LLM agent regression testing · prompt regression testing · model-swap testing for AI
agents · LLM evaluation · LLMOps · CI gate for prompt and model changes · selective replay ·
false-negative rate · LangGraph · MLflow · CrewAI · OpenAI Agents SDK · OpenTelemetry · Ollama ·
OpenAI · Anthropic · Python.
