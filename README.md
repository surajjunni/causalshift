# ReplayGate

[![CI](https://github.com/surajjunni/replaygate/actions/workflows/ci.yml/badge.svg)](https://github.com/surajjunni/replaygate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)

**Check if a prompt or model change made your AI agent worse, before you ship it.**

You change a prompt, or switch models. Your tests pass. But did the agent quietly get worse on
real questions? ReplayGate tells you, using your agent's own past runs.

📝 **Launch post:** [Your agent's prompt change passed CI. Did it actually get *worse*?](https://surajjyothiunni1.substack.com/p/your-agents-prompt-change-passed)

## How it works

1. You record some real runs of your agent (once).
2. You make a change: a new prompt, or a new model.
3. ReplayGate replays those runs with the change and gives you one of three answers:
   - **PASS** — safe to ship.
   - **FAIL** — it got worse.
   - **NOT SURE** — it won't guess, so it blocks the deploy.

It's fast because it only re-runs the steps your change can affect, and reuses the rest.

Drop it into CI and read the exit code: `0` safe, `1` worse, `2` not sure.

## Install

```bash
uv venv && uv pip install -e ".[dev]"   # or: pip install -e ".[dev]"
```

## Try it

Record your runs into `trajectories.json` (see **Record your runs** below), then run:

```bash
replaygate ingest trajectories.json
replaygate diff --workflow W --intervention change.json --backend ollama
```

You get a short report:

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

A few things to know:

- `change.json` says what you changed (which step's prompt or model).
- `--backend` is the model that re-runs the changed steps: `ollama` (on your machine), or `openai`
  / `anthropic`. For the cloud ones, put your key in `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`. If a
  key is missing, ReplayGate says NOT SURE instead of guessing.
- Handy flags: `--margin` (how big a drop counts as "worse"), `--format markdown` (paste the report
  into a pull request), `--json` (for scripts).

## Record your runs

ReplayGate needs a recording of your agent running. You add one thing: for each step, say what it
needs. Everything else is recorded for you.

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

**On LangGraph?** Capture straight from your graph, with almost no code:

```python
from replaygate.adapters.langgraph import trace_from_langgraph

app = graph.compile()
trace = trace_from_langgraph(app, inputs=[{"q": q} for q in questions])
# -> save to JSON for `replaygate ingest`
```

LangGraph steps share data, so a recording may miss some links between steps. ReplayGate notices,
marks that recording "unverified", and will not hand you a confident PASS from it (it says NOT SURE)
unless you pass `--accept-unverified-deps`. Add the missing links, or use the setup above, for a
fully checked run. See `examples/langgraph_agent.py`.

## Works with

| Framework | How to capture | Example |
|---|---|---|
| **LangGraph** | `adapters.langgraph.trace_from_langgraph(app, inputs)` | `examples/langgraph_agent.py` |
| **MLflow Tracing** | `adapters.mlflow.trace_from_mlflow(traces)` | `examples/mlflow_agent.py` |
| **CrewAI** | `adapters.crewai.trace_from_crewai(tasks, crew.kickoff())` | `examples/crewai_agent.py` |
| **OpenAI Agents SDK / LlamaIndex / OpenTelemetry** | turn spans into `{name, parent, output}` and call `adapters.spans.trace_from_spans(traces)` | span recipe below |

Every example runs with **no framework installed** (stand-ins mirror the real shape), so you can see
how capture works first, then swap in your real app.

```python
from replaygate.adapters.spans import trace_from_spans
# each run is a list of spans; a span is {"name", "parent": <parent name or None>, "output"}
trace = trace_from_spans([[{"name": "retrieve", "parent": None, "output": docs},
                           {"name": "answer", "parent": "retrieve", "output": ans}]])
```

## It tells you when it might be wrong

ReplayGate saves time by reusing old results for steps your change can't touch. That is safe only if
it knows how the steps connect. If a connection is missing, it could reuse a stale result and miss a
real problem.

ReplayGate is upfront about this:

- It **measures how often it misses**, on a test with known answers: `replaygate benchmark`.
- When it isn't sure a step is safe to reuse, it **re-runs the step**.
- You can always do a **full re-run** with `--mode full`: slower, but always correct.

## Compared to other tools

- Tools that replay recorded outputs catch wiring bugs, but can't test a prompt or model *change*
  (the recording is the very thing the change would alter). ReplayGate tests the change.
- Tools like DeepEval and promptfoo compare prompts on hand-written examples. ReplayGate uses your
  real past runs instead.

## What it supports

Agents whose steps run in a simple one-way order (no loops), where you've said how the steps connect.
Loops and hidden-state agents are turned away, not guessed at. The guiding rules are in
`.specify/memory/constitution.md`.

---

**Keywords:** LLM agent regression testing · prompt regression testing · model-swap testing for AI
agents · LLM evaluation · LLMOps · CI gate for prompt and model changes · selective replay ·
false-negative rate · LangGraph · MLflow · CrewAI · OpenAI Agents SDK · OpenTelemetry · Ollama ·
OpenAI · Anthropic · Python.
