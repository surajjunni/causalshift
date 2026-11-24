# Your agent's prompt change passed CI. Did it actually get *worse*?

### ReplayGate: regression testing for LLM agents — on your real traffic, before you ship. And it tells you how often it might be *wrong*.

---

You tweak a system prompt. Or you upgrade `gpt-4o` to the next model. Your tests
go green. You ship.

But your agent is a multi-step thing — plan, retrieve, call a tool, write the
answer — and it's non-deterministic. There's no unit test that tells you whether
that one prompt edit quietly made 1 in 5 answers worse. Most teams find out from
users. Or they don't find out at all.

The honest state of the art for "did my change break the agent" is one of three
unsatisfying options:

- **Hand-written eval sets.** Useful, but you never write enough of them, and
  they're not your real traffic.
- **Full re-execution.** Re-run the whole agent on a corpus for every change.
  Correct, but slow and expensive.
- **Replaying recorded outputs.** Cheap, but it *can't* test a model or prompt
  change — the recording is exactly what the change would alter.

I built **ReplayGate** to sit in the gap: test a model/prompt change against your
**real recorded traffic**, cheaply, and — this is the part I care about most —
**tell you how trustworthy the answer is.**

[github.com/surajjunni/replaygate](https://github.com/surajjunni/replaygate) · MIT · Python

## The one command

You record some real agent runs (a two-line instrumentation seam, or an adapter
for LangGraph / MLflow / CrewAI). Then you ask: is this change safe?

```
$ replaygate diff --workflow support --intervention bad_prompt.json --backend ollama --evaluator judge

ReplayGate — change risk report [support]
  verdict:      FAIL — quality regresses
  impact:       -0.675 mean quality (95% CI [-0.850, -0.500])
  changed step: responder
  cost:         selective made 4 model call(s); full re-execution ≈ 12 (saved ~8, 67%)
  reuse:        exposure 0.75 (fraction of nodes reused) — an exposure measure, not a miss probability
  exit:         1  (0 PASS / 1 FAIL / 2 INCONCLUSIVE)
```

That exit code drops straight into CI. `0` ships, `1` blocks, and `2` — **you
couldn't tell** — also blocks.

## How it works: selective causal replay

Full re-execution is the sound-but-slow baseline: re-run every step. ReplayGate's
trick is to recompute **only the steps the change can actually affect** and reuse
the recorded output everywhere else — but *only* where reuse is provably valid. A
node is reused only if its inputs are unchanged; if validity is uncertain, it
recomputes. Fail toward recompute, never toward a false "safe."

On a synthetic benchmark with injected faults and **independent** ground truth,
selective replay agrees with full re-execution on **97.6%** of cases while using
about **43%** of the model calls. On a small live run (llama3, a real 4-step
text agent), a deliberately bad prompt was caught by both modes — selective in
**4** model calls versus full's **12**.

## The part most tools skip: how often is it *wrong*?

Here's the catch, and ReplayGate puts it on the front page instead of in a
footnote. Reuse is only as sound as your **declared dependency graph**. If a step
secretly reads something a non-obvious upstream step produced — a *missing edge* —
selective replay can reuse a stale output and **miss a real regression**.

So the headline metric isn't the hit rate. It's the **false-negative rate**:
how often does the tool say "safe" when it wasn't? ReplayGate measures it against
ground truth and reports it with a **Wilson confidence interval**, across
topologies and across how frequently those hidden edges occur. The finding is
exactly what you'd expect, stated plainly:

| hidden-edge frequency | false-negative rate |
|---|---|
| 0% | 0.00 |
| 10% | 0.10 |
| 25% | 0.25 |
| 50% | 0.50 |

**Your miss rate tracks how complete your dependency graph is — not how clever
the tool is.** That's not a great marketing line. It's the true one, and it's the
number you should demand from anything that claims to gate your deploys.

Two more non-negotiables fall out of the same principle:

- **Fail closed.** No evidence, too few samples, or a backend that couldn't
  recompute → `INCONCLUSIVE`, which blocks. An empty run is never a silent pass.
- **Measured, not asserted.** Every accuracy and efficiency claim is checked
  against a reproducible benchmark; the "exposure" number is labeled as exposure,
  not disguised as a probability.

## Where it fits (and where it doesn't)

ReplayGate is complementary to the tools you know, and I'd rather say so than
pretend it replaces them:

- Replay-and-gate tools like **Tracely** catch *orchestration* regressions by
  replaying recorded outputs — by design they can't test a model/prompt change.
- **DeepEval / promptfoo** compare models and prompts, but on hand-written cases,
  not your real traffic.
- **CAR** and **CausalFlow** attribute *which step caused a single run's failure*.
  ReplayGate isn't competing with them on single-run attribution — it answers the
  **deployment** question across a population, cheaply.

Scope, honestly: v1 supports deterministic, explicitly instrumented **DAG-style**
agents. Cyclic and opaque-stateful agents are rejected, not silently (and wrongly)
analyzed.

## Try it

```bash
pip install -e ".[dev]"
python examples/instrumented_agent.py     # or langgraph / mlflow / crewai examples
replaygate ingest trace.json
replaygate diff --workflow W --intervention change.json --backend ollama
```

Capture works with the lightweight seam (declare each node's dependencies once)
or zero-rewrite adapters for LangGraph, MLflow Tracing, CrewAI, the OpenAI Agents
SDK, and OpenTelemetry. Recompute runs on local Ollama or cloud models.

## Honest status

This is early. The headline benchmark is synthetic (that's how you *get* ground
truth to measure a false-negative rate at all); the live run is small and the
LLM-judge is itself noisy; the cloud (OpenAI/Anthropic) backends are scaffolded
but not yet exercised against the live APIs; and the MLflow/CrewAI adapters are
validated against documented object shapes, not every framework version. All of
that is written down in the repo, not hidden.

If you run multi-step LLM agents in production and dread the "did this change
break something" question, I'd love for you to point it at your traces and tell
me where it's wrong — especially where the dependency graph is harder to declare
than my benchmark pretends.

**→ [github.com/surajjunni/replaygate](https://github.com/surajjunni/replaygate)**
