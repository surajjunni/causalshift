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

```bash
causalshift ingest trajectories.json                 # validate + load (rejects cyclic/out-of-contract)
causalshift evaluate --workflow W --intervention change.json --mode selective --backend ollama
causalshift benchmark                                # the injected-fault quality gate
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
predicate consumes, so a captured trace is immediately replayable. Runnable
end-to-end (no LLM) in `examples/instrumented_agent.py`.

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
