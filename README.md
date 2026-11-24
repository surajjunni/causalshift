# CausalShift

**Causal regression testing for model and prompt changes in LLM-agent pipelines.**

> You're about to swap a model or edit a prompt behind a production agent. On
> your *real* recorded traffic — not hand-written test cases — will quality
> regress, which step is responsible, and can you find out cheaply?

CausalShift replays recorded agent trajectories under a proposed change,
recomputes only the **causally-affected** nodes (reusing recorded outputs
elsewhere *only when provably valid*), and reports: did quality regress
(with a confidence interval), which decision caused it, and the **measured
false-negative risk** of any reuse.

## Install

```bash
uv venv && uv pip install -e ".[dev]"   # or: pip install -e ".[dev]"
```

## Use

**Is this change safe? (one command)** — the front door:

```bash
causalshift ingest trajectories.json                 # validate + load (rejects cyclic/out-of-contract)
causalshift diff --workflow W --intervention change.json --backend ollama --evaluator judge
```

```text
CausalShift — change risk report [W]
  verdict:      FAIL — quality regresses
  impact:       -0.675 mean quality (95% CI [-0.850, -0.500])
  changed step: responder
  cost:         selective made 4 model call(s); full re-execution ≈ 12 (saved ~8, 67%)
  reuse:        exposure 0.75 (fraction of nodes reused) — an exposure measure, not a miss probability
  exit:         1  (0 PASS / 1 FAIL / 2 INCONCLUSIVE)
```

Exit codes gate CI directly (0 pass / 1 fail / 2 inconclusive-fails-closed). Lower-level commands:

```bash
causalshift evaluate --workflow W --intervention change.json --mode selective --backend ollama
causalshift benchmark                                # the injected-fault quality gate
```

**Recompute backends** (`--backend`): `none` (default), `ollama` (local),
`openai`, `anthropic`. Cloud backends read the key from the environment
(`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`) — never passed on the command line or
logged — and **fail closed**: with no key (or any API error) the affected nodes
are inconclusive and the run exits 2, never a silent pass. Cloud backends are
offline-tested (fallback + parsing) but not yet exercised against the live APIs;
validate against your account.

```bash
export OPENAI_API_KEY=...   # your shell, not CausalShift
causalshift diff --workflow W --intervention change.json --backend openai --evaluator judge
```

See `specs/001-causal-regression-core/quickstart.md` for runnable scenarios and
`specs/001-causal-regression-core/contracts/` for the input/backend/CLI contracts.

## Instrumenting your agent (the light seam)

Capturing a trace is the one thing a user must add. The seam is deliberately
small: **declare each node's dependencies once**, and inputs, outputs and
fingerprints are captured automatically.

```python
from causalshift.instrument import InstrumentedAgent

agent = InstrumentedAgent("support")

@agent.node("planner", deps=["question"], prompt_id="plan.v1", prompt="Plan how to answer.")
def planner(question): ...

@agent.node("responder", deps=["planner"], prompt_id="respond.v1", prompt="Answer using the plan.")
def responder(planner): ...

for i, q in enumerate(questions):
    with agent.trajectory(f"t{i}") as run:
        run.set("question", q)   # a source input
        run.run_all()            # runs nodes in dependency order, capturing each

agent.save("trace.json")         # ready for `causalshift ingest`
```

Declared `deps=` are the dependency edges — the honest level of instrumentation
(explicit DAG). The emitted fingerprints are exactly what the replay validity
predicate consumes, so a captured trace is immediately replayable.

- `examples/instrumented_agent.py` — the seam on a pure-Python agent (no LLM).
- `examples/live_agent.py --evaluate` — the seam on a live Ollama agent, which
  records a trace *and* evaluates a prompt change end to end. Measured (llama3,
  4 trajectories): both modes detect the regression; **selective 4 recompute
  calls vs full 12** (same prompt-construction for record and replay).

### From a framework: LangGraph (near-zero code)

Already on LangGraph? Capture a trace from a compiled graph with no node rewrites:

```python
from causalshift.adapters.langgraph import trace_from_langgraph

app = graph.compile()
trace = trace_from_langgraph(app, inputs=[{"q": q} for q in questions])
# -> store.workflow_from_dict(trace), or dump to JSON for `causalshift ingest`
```

The graph's nodes/edges become the declared dependency DAG and `app.stream(...)`
captures each node's output. **Caveat:** LangGraph nodes share one state object,
so control-flow edges can under-declare true data dependencies (the missing-edge
risk) — which `reuse_exposure` and the benchmark then measure, not hide. For
nodes with hidden cross-state reads, add the edges or use the explicit seam.
`examples/langgraph_agent.py` runs with no LLM. Install: `pip install "causalshift[langgraph]"`.

### Other frameworks

| Framework | How | Status |
|---|---|---|
| **LangGraph** | `adapters.langgraph.trace_from_langgraph(app, inputs)` | live-tested |
| **MLflow Tracing** | `adapters.mlflow.trace_from_mlflow(traces)` (span_id/parent_id → edges) | shim over the span core; validate vs your MLflow version |
| **CrewAI** | `adapters.crewai.trace_from_crewai(tasks, crew.kickoff())` — task `context` → edges | validate vs your CrewAI version |
| **OpenAI Agents SDK / LlamaIndex / OpenTelemetry** | normalize their spans to `{name, parent, output}` and call `adapters.spans.trace_from_spans(traces)` | generic span core (tested) |

Span-based recipe (covers any tracing stack):

```python
from causalshift.adapters.spans import trace_from_spans
# each trajectory = a list of spans; span = {"name", "parent": <parent node name|None>, "output"}
trace = trace_from_spans([[{"name": "retrieve", "parent": None, "output": docs},
                           {"name": "answer", "parent": "retrieve", "output": ans}]])
```

Same soundness caveat applies to all: a span/parent tree is control-flow, so it
can under-declare true data dependencies — measured by `reuse_exposure` and the
benchmark, not hidden. The span core is tested; the per-framework shims are
validated against documented object shapes — confirm against your installed
version (and open an issue if a field moved).

## How it relates to other tools (honest scope)

CausalShift occupies a gap the adjacent tools state they do **not** fill:

- **Tracely and the `agent-replay` family** replay *recorded* model outputs to
  catch orchestration regressions. By design they cannot test a **model/prompt
  change** (the recorded output is invalid once the model changes); they point
  you to live experiments for that. CausalShift *is* that live-but-cheap path.
- **DeepEval / promptfoo** compare models/prompts, but on **hand-written test
  cases**. CausalShift uses your **real recorded traffic** instead.
- **CAR (arXiv 2606.08275) and CausalFlow (arXiv 2605.25338)** attribute *which
  step caused a single run's failure*. CausalShift is **not** competing with
  them on general single-run attribution — it answers the **deployment**
  question (is change B safe across a population) and contributes
  **dependency-aware selective replay** (fewer model calls than full
  re-execution), with its own soundness measured.

## The honest caveat

Reuse is only as sound as the declared dependency graph. If a true dependency
is undeclared (a *missing edge*), selective replay can reuse a stale output and
**miss a regression**. CausalShift does not hide this: the false-negative rate
is the headline metric, measured against ground truth by `causalshift
benchmark`, and the engine fails toward recompute whenever validity is
uncertain. Full re-execution (`--mode full`) is always available as the sound,
if slower, oracle.

v1 scope: deterministic, explicitly instrumented **DAG-style** agents. Cyclic
and opaque-stateful agents are rejected, not silently analyzed. See
`.specify/memory/constitution.md` for the governing principles.
