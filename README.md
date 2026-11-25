# ReplayGate

[![CI](https://github.com/surajjunni/replaygate/actions/workflows/ci.yml/badge.svg)](https://github.com/surajjunni/replaygate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)

**Did a change to your AI app make it worse? Check before you ship it.**

You change a prompt or swap the model behind your AI app to improve it, and your tests pass. But a
small change can quietly make the answers *worse*, and ordinary tests often miss it because the AI
doesn't answer the same way every time.

**ReplayGate catches it.** You give it the change you're about to make, and it checks that change
against your app's **real past runs**. Then it tells you one of three things: safe, worse, or not sure.

📝 **Launch post:** [Your agent's prompt change passed CI. Did it actually get *worse*?](https://surajjyothiunni1.substack.com/p/your-agents-prompt-change-passed)

## How it works

1. You record some real runs of your agent (you do this once).
2. You make a change: a new prompt, or a new model.
3. ReplayGate replays those recorded runs with your change and answers:
   - **PASS** — safe to ship.
   - **FAIL** — it got worse.
   - **NOT SURE** — it won't guess, so it stops the change.

It's fast because it only re-runs the steps your change can actually affect.

## Install

```bash
uv venv && uv pip install -e ".[dev]"   # or: pip install -e ".[dev]"
```

This installs ReplayGate. You need Python 3.12 or newer.

## Try it

It's two commands:

```bash
replaygate ingest trajectories.json
replaygate diff --workflow support-bot --intervention change.json --backend ollama
```

Here's what every part means:

- **`trajectories.json`** — the recording of your agent's past runs. You make this once (see
  *Record your runs* below). *(A "trajectory" is just one run of the agent from start to finish.)*
- **`replaygate ingest`** — loads that recording so ReplayGate can use it.
- **`replaygate diff`** — the main command. It asks: *is this change safe?*
- **`--workflow support-bot`** — the name of your agent (whatever you called it when recording).
- **`--intervention change.json`** — a small file that describes the change you want to test (which
  step's prompt or model you're changing, and the new value). Example below.
- **`--backend ollama`** — which AI actually re-runs the changed steps. `ollama` runs a model on
  your own computer. You can also use `openai` or `anthropic` (put your API key in an environment
  variable; if it's missing, ReplayGate says NOT SURE instead of guessing).

You'll get a short report:

```text
ReplayGate — change risk report [support-bot]

  ✗ FAIL — quality regresses
  → Don't ship: quality regresses — the 95% CI is entirely past the margin.

  change:       responder
  impact:       -0.675 mean quality (95% CI [-0.850, -0.500], margin -0.000) — candidate scores 0.675 lower on average
  cost:         selective made 4 model call(s); full re-execution ≈ 12 (saved ~8, 67%)
  reuse:        exposure 0.75 — fraction of nodes reused, not a miss probability
  exit:         1  (0 PASS / 1 FAIL / 2 INCONCLUSIVE)
```

The last line is an **exit code** you can use in automation: `0` safe, `1` worse, `2` not sure.

**What `change.json` looks like:**

```json
{
  "targets": { "responder": { "prompt_id": "respond.v2" } },
  "prompts": { "respond.v2": "Answer in a single short sentence." }
}
```

This says: *change the `responder` step's prompt to this new text, and test it.*

Other handy options: `--margin` (how big a drop counts as "worse"), `--format markdown` (a version
you can paste into a GitHub pull request), `--json` (for scripts).

## Record your runs

ReplayGate needs a recording of your agent running. You add one small thing: for each step, say
what it needs. Everything else is recorded for you.

```python
from replaygate.instrument import InstrumentedAgent

agent = InstrumentedAgent("support-bot")

# deps=[...] lists what each step needs. "planner" needs the question;
# "responder" needs the planner's output.
@agent.node("planner", deps=["question"], prompt_id="plan.v1", prompt="Plan how to answer.")
def planner(question): ...

@agent.node("responder", deps=["planner"], prompt_id="respond.v1", prompt="Answer using the plan.")
def responder(planner): ...

for i, q in enumerate(questions):
    with agent.trajectory(f"t{i}") as run:
        run.set("question", q)   # a starting input
        run.run_all()            # runs the steps in order and records each one

agent.save("trajectories.json")  # this is the file you pass to `replaygate ingest`
```

**Using LangGraph?** You can record straight from your graph, with almost no extra code:

```python
from replaygate.adapters.langgraph import trace_from_langgraph

app = graph.compile()
trace = trace_from_langgraph(app, inputs=[{"q": q} for q in questions])
# -> save to JSON for `replaygate ingest`
```

One honest note for LangGraph: its steps share data, so a recording can miss some links between
steps. ReplayGate notices, marks that recording "unverified", and will **not** give you a confident
PASS from it (it says NOT SURE) unless you add `--accept-unverified-deps`. Add the missing links, or
use the setup above, for a fully checked run. See `examples/langgraph_agent.py`.

## Works with

| Framework | How to record | Example |
|---|---|---|
| **LangGraph** | `adapters.langgraph.trace_from_langgraph(app, inputs)` | `examples/langgraph_agent.py` |
| **MLflow Tracing** | `adapters.mlflow.trace_from_mlflow(traces)` | `examples/mlflow_agent.py` |
| **CrewAI** | `adapters.crewai.trace_from_crewai(tasks, crew.kickoff())` | `examples/crewai_agent.py` |
| **OpenAI Agents SDK / LlamaIndex / OpenTelemetry** | turn spans into `{name, parent, output}` and call `adapters.spans.trace_from_spans(traces)` | span recipe below |

Every example runs with **no framework installed** (stand-ins mirror the real shape), so you can
see how recording works first, then swap in your real app.

```python
from replaygate.adapters.spans import trace_from_spans
# each run is a list of spans; a span is {"name", "parent": <parent name or None>, "output"}
trace = trace_from_spans([[{"name": "retrieve", "parent": None, "output": docs},
                           {"name": "answer", "parent": "retrieve", "output": ans}]])
```

## It tells you when it might be wrong

ReplayGate is fast because it reuses old results for the steps your change can't touch. That's only
safe if it knows how the steps connect. If a connection is missing, it could reuse an old result and
miss a real problem.

ReplayGate is upfront about this:

- It **measures how often it misses**, on a test with known answers: `replaygate benchmark`.
- When it isn't sure a step is safe to reuse, it **re-runs the step** instead of guessing.
- You can always do a **full re-run** with `--mode full`: slower, but always correct.

## Compared to other tools

- Some tools replay recorded outputs to catch wiring bugs, but they can't test a prompt or model
  *change* (the recording is the very thing the change would alter). ReplayGate tests the change.
- Tools like DeepEval and promptfoo compare prompts on hand-written examples. ReplayGate uses your
  real past runs instead.

## What it supports

Agents whose steps run in a simple one-way order (no loops), where you've said how the steps
connect. Loops and hidden-state agents are turned away, not guessed at. The guiding rules are in
`.specify/memory/constitution.md`.

---

**Keywords:** LLM agent regression testing · prompt regression testing · model-swap testing for AI
agents · LLM evaluation · LLMOps · CI gate for prompt and model changes · selective replay ·
false-negative rate · LangGraph · MLflow · CrewAI · OpenAI Agents SDK · OpenTelemetry · Ollama ·
OpenAI · Anthropic · Python.
