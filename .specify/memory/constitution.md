# ReplayGate Constitution

ReplayGate is an open-source tool for **causal regression testing of model and prompt
changes in LLM-agent pipelines**: given a proposed change (model A → B, or a prompt edit),
it replays recorded production trajectories, recomputes only the causally-affected steps,
and reports whether agents regress, which decision is responsible, and with what confidence.

## Core Principles

### I. Soundness Over Savings (NON-NEGOTIABLE)

A tool that reports "safe to deploy" and is wrong is worse than no tool at all. Therefore the
**false-negative rate — regressions missed because the tool reused state it should have
recomputed — is the headline metric** and MUST always be measured and reported alongside any
result. Cost, latency, and call-count savings MUST NEVER be obtained by widening the set of
reused steps in a way that is not proven sound; when soundness and savings conflict, soundness
wins. Any release MUST state the measured false-negative rate (or an upper bound) for its
benchmark; a release that cannot MUST NOT claim deployment-safety verdicts.

### II. Reuse When Justified, Recompute When Necessary, Quantify the Rest

This is the defining engineering principle. A recorded step's output MAY be reused ONLY when
its relevant inputs and environmental assumptions are provably still valid under the
intervention. All causally-affected nodes MUST be recomputed. When dependency validity is
uncertain, the system MUST escalate to broader recomputation rather than reuse (fail toward
recompute, never toward reuse). Every reuse decision MUST record the justification (which
dependencies held) so it can be audited.

### III. Measured, Not Asserted (NON-NEGOTIABLE)

Measured facts and modeling assumptions MUST be distinguished everywhere — in code, docs, and
tool output. Every accuracy or efficiency claim (e.g. "selective replay matches full
re-execution at lower cost") MUST be validated against ground truth via injected-fault
benchmarks before it ships, and MUST carry quantified uncertainty (confidence intervals;
real effect separated from sampling noise). No claim ships unvalidated; "we believe" is not a
result.

### IV. Scope Honesty

v1 targets **deterministic, explicitly instrumented, DAG-style agents only**. The tool MUST NOT
claim sound selective replay for arbitrary stateful or cyclic agents until the dependency model
provably supports them; until then such agents MUST be rejected or clearly flagged as
out-of-contract rather than silently analyzed. Capabilities MUST be described by what is tested,
not by what is aspired to.

### V. Complementary & Honest Positioning

ReplayGate MUST be positioned honestly against adjacent work (CAR, CausalFlow, Tracely,
DeepEval) and MUST NOT overstate novelty. Its defensible contribution is the **deployment-decision
question** (is change B safe on real traffic, and which step breaks) plus the **efficiency result**
(dependency-aware selective replay vs full re-execution), delivered as a usable tool. Explicit
non-goal: competing with CAR or CausalFlow on general-purpose single-run causal attribution.

## Scope & Boundaries (v1)

- **In scope:** deterministic, explicitly instrumented DAG-style agent trajectories; model/prompt
  interventions at named nodes; selective recomputation with uncertainty-aware escalation;
  population-level regression effect with confidence intervals; regression attribution to the
  responsible decision(s).
- **Out of scope (v1):** sound selective replay for cyclic or opaque-stateful agents;
  general-purpose single-run failure attribution; live production monitoring; automatic repair.
- **Honesty obligation:** anything out of scope MUST be stated as such in user-facing output, not
  silently approximated.

## Development Workflow & Quality Gates

- **Ground-truth benchmark is the gate.** The primary benchmark compares selective replay against
  full re-execution on workflows with injected faults, measuring: regression-detection agreement,
  **missed regressions (false negatives)**, attribution accuracy, token cost, model-call count, and
  wall-clock latency. A change that worsens the false-negative rate MUST NOT merge without explicit,
  documented justification.
- **Reproducibility.** Results MUST be reproducible from the repo (seeded, scripted, no paid-API
  dependency required to run the core benchmark).
- **Claims traceability.** Every claim in README/docs MUST point to the test or benchmark that
  backs it; unbacked claims are defects.
- **Separation of measured vs assumed** MUST be preserved through the pipeline into reports.

## Governance

This constitution supersedes other practices for ReplayGate. Amendments MUST be documented in the
Sync Impact Report, versioned per semantic versioning (MAJOR: principle removal/redefinition;
MINOR: new principle/section or materially expanded guidance; PATCH: clarifications), and dated.
All substantial changes (PRs) MUST verify compliance with these principles — in particular that no
deployment-safety claim ships without a measured false-negative rate, and that no capability claim
exceeds what the tests cover. Complexity or any widening of state-reuse MUST be justified against
Principle I.

**Version**: 1.0.0 | **Ratified**: 2026-11-23 | **Last Amended**: 2026-11-23
