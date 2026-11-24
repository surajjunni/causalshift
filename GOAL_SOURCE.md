# ReplayGate — goal & charter

**Causal regression testing for model and prompt changes in LLM-agent pipelines.**

> If we deploy model B instead of model A (or change a prompt), will our agents
> regress, which decisions are responsible, and can we know that *without
> replaying everything*?

## Why this, and not another replay/attribution framework

The adjacent work is already strong, so ReplayGate is scoped against it, not
over it:

| | Question it answers |
|---|---|
| CAR (arXiv 2606.08275), CausalFlow (arXiv 2605.25338) | *Within one run, which step caused this failure?* |
| Tracely, the `agent-replay` repos | *Did orchestration break?* (replays recorded model outputs, so a model change is invisible) |
| DeepEval, promptfoo | *Did quality change?* — on hand-written test cases, not real traffic |
| **ReplayGate** | ***If I swap model/prompt, will my agents regress on real traffic, which decision is responsible, and can I decide cheaply?*** |

**Non-goal:** competing with CAR or CausalFlow on general-purpose single-run
causal attribution. We borrow their intervention/attribution machinery and
point it at the deployment question.

## The central technical contribution

**Dependency-aware selective counterfactual replay.**

Full re-execution (CAR-style) reruns the whole trajectory forward after an
intervention. ReplayGate instead builds a **dependency graph** over agent
decisions and **reuses a recorded step's output only when its relevant inputs
and environmental assumptions are still valid**; it recomputes only the
causally-affected nodes. This is the fix for the weak assumption in the current
engine (today it marks *everything* after a divergence as off-cassette).

Defining principle: **reuse when justified, recompute when necessary, and
quantify what remains uncertain.**

### The measurable hypothesis

> Selective causal replay preserves regression-detection and attribution
> accuracy relative to full re-execution while reducing LLM calls, latency, and
> evaluation cost.

### The load-bearing caveat (soundness)

Reusing an unaffected step must be **sound**. If a real dependency is missing
from the graph, selective replay can **silently miss a regression** — a false
"safe to deploy." This is the central risk of the whole approach and must be
treated as a first-class concern, not a footnote:

- Every reuse decision records *why* it was judged safe (which dependencies held).
- **Uncertainty-aware replay escalation:** when dependency validity is
  uncertain, automatically fall back to broader recomputation rather than
  reuse. Cheaper when confident, safe when not.
- The benchmark must explicitly measure missed regressions (false negatives),
  not only cost savings.

## Core capabilities (what the tool does)

1. **Capture traces with dependencies** — record agent runs *and* the
   input→output dependencies between steps (needs a light instrumentation seam,
   like Tracely's `call_llm`/`call_tool`, so real inputs are retained — the
   thing the current corpus dropped).
2. **Intervene** — substitute a model or prompt at a chosen node.
3. **Selectively recompute** — rerun only causally-affected nodes; reuse valid
   recorded state elsewhere, with escalation when validity is uncertain.
4. **Evaluate across many trajectories** — population-level, not one run.
5. **Quantify uncertainty** — regression magnitude with confidence intervals;
   separate real degradation from sampling noise.
6. **Explain** — attribute a regression to the responsible decision(s).

## Primary benchmark

Compare **selective replay vs full re-execution** on agent workflows with
**injected faults** (known ground truth):

- regression-detection agreement (incl. **missed regressions / false negatives**)
- causal attribution accuracy
- token cost, number of model calls, wall-clock latency

Success = statistically indistinguishable detection/attribution accuracy at a
materially lower call/latency/cost budget — *and* a bounded, measured
false-negative rate.

## Scope (v1)

- **In:** deterministic, explicitly instrumented **DAG-style** agents.
- **Out (for now):** sound selective replay for arbitrary **stateful or cyclic**
  agents — not claimed until the dependency model supports them.

## What this reuses from the existing engine

This is an evolution of the `real_traces/` replay harness, not a rewrite:

| Need | Already have (`store/`, `replay/`) |
|---|---|
| Trace store, lossless, queryable | `store/tracedb.py` + parity gate |
| Replay loop, exact + counterfactual | `replay/replayer.py` |
| Divergence detection | counterfactual mode (today: conservative) |
| Tiered recompute (live model) | `replay/responder.py` + `replay/ollama_backend.py` |
| Severity / drift measurement | `replay/drift.py` |
| Savings-vs-fidelity sweep | `replay/frontier.py` |

**New work required:** (a) the dependency graph + the soundness/validity model;
(b) selective recompute + escalation replacing the conservative propagation;
(c) the instrumentation seam that captures real inputs; (d) population-level
causal-effect estimation with uncertainty; (e) the injected-fault benchmark.

## Honest risks

- **Soundness is the whole ballgame.** A tool that says "safe to deploy" and is
  wrong is worse than no tool. The false-negative rate is the headline metric.
- **Dependency extraction is hard** for real agents; v1 leans on explicit
  instrumentation and does not over-claim generality.
- **The research framing is contested** (CAR/CausalFlow are active). The
  defensible wedge is the *deployment* question + the *efficiency* result, as a
  usable tool — not out-publishing single-run attribution.
