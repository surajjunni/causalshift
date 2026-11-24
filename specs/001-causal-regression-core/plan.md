# Implementation Plan: Causal Regression Core

**Branch**: `001-causal-regression-core` | **Date**: 2026-11-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-causal-regression-core/spec.md`

## Summary

Given recorded, instrumented DAG-style agent trajectories and a proposed
model/prompt change, CausalShift produces a population-level regression verdict
(regressed? magnitude + confidence interval), attributes it to the responsible
node(s), and does so via **dependency-aware selective replay** that recomputes
only causally-affected nodes and reuses recorded outputs only when provably
valid — always reporting the reuse exposure (fraction reused; not a miss
probability — the false-negative rate is benchmark-measured). A sound
full re-execution path is the baseline and the correctness oracle; an
injected-fault benchmark with known ground truth is the primary quality gate.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: standard library first; `networkx` for the dependency
DAG; `numpy` for bootstrap confidence intervals. No web/infra frameworks.

**Storage**: SQLite (stdlib `sqlite3`) for the trace store, normalized schema;
documented migration path to DuckDB if analytical sweeps demand it.

**Testing**: `pytest` for deterministic unit/integration tests; the
injected-fault benchmark harness is the primary quality gate (seeded,
reproducible, offline-runnable).

**Target Platform**: local CLI / library (macOS, Linux). No server.

**Project Type**: single Python package (library + CLI).

**Performance Goals**: selective replay reaches the full-re-execution verdict
using strictly fewer model calls than the fair single-pass baseline (SC-003;
measured ratio reported); core benchmark runs offline without paid APIs.

**Constraints**: soundness is gating — no state reuse without a validity proof;
recompute backend (local model, e.g. Ollama) is pluggable and MUST degrade
gracefully when unavailable; every claim validated against ground truth with
quantified uncertainty.

**Scale/Scope**: v1 = deterministic DAG agents, tens–hundreds of trajectories
per evaluation, single-digit-to-dozens of nodes per trajectory.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Soundness Over Savings | Selective replay reuses a step ONLY behind a validity predicate; uncertain → recompute; reuse_exposure reported every run and the false-negative RATE measured by the benchmark; inconclusive runs fail closed. Single-pass full re-execution is the sound oracle. | PASS (enforced in `replay/` + `soundness/`; CLI exit 2 on inconclusive) |
| II. Reuse/Recompute/Quantify | Every reuse decision records its justification; escalation on uncertainty is the default. | PASS |
| III. Measured, Not Asserted | Injected-fault benchmark with ground truth backs all SC claims; CIs via bootstrap; reports tag measured vs assumed. | PASS (enforced in `benchmark/` + `report/`) |
| IV. Scope Honesty | DAG-only; cyclic/opaque-stateful trajectories rejected/flagged (FR-011). | PASS |
| V. Complementary Positioning | README scopes vs CAR/CausalFlow/Tracely/DeepEval; no novelty overstatement. | PASS (docs task) |

No violations → Complexity Tracking omitted.

## Project Structure

### Documentation (this feature)

```text
specs/001-causal-regression-core/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── trace-input.md       # the instrumented-trajectory input contract
│   ├── recompute-backend.md # the pluggable recompute backend interface
│   └── cli.md               # CLI command contract
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/causalshift/
├── store/          # SQLite trace store: ingest instrumented trajectories, schema
├── graph/          # dependency-DAG model over steps; causal-closure (affected set)
├── intervene/      # intervention engine: substitute model/prompt at named nodes
├── backends/       # recompute backends: base interface, local (ollama), unavailable
├── replay/         # single-pass full re-execution + dynamic selective replay + validity predicate
├── soundness/      # reuse-exposure + false-negative accounting ledger
├── instrument.py   # light instrumentation seam: @node(deps=...) auto-captures traces (FR-014)
├── evaluate/       # population evaluator; bootstrap confidence intervals
├── attribute/      # regression attribution to responsible node(s)
├── report/         # reporting layer; measured-vs-assumed tagging
└── cli.py          # CLI entry point

benchmark/
├── faults/         # injected-fault generators (known ground truth)
├── fixtures/       # seeded synthetic DAG trajectories
└── run_benchmark.py# selective vs full comparison harness (primary gate)

tests/
├── unit/
└── integration/
```

**Structure Decision**: Single pip-installable Python package `causalshift`
(library + `cli.py` entry point), with `benchmark/` and `tests/` at repo root.
The module boundaries mirror the ten architecture components in the spec, with
soundness isolated in its own module so the false-negative accounting is never
entangled with the replay logic it audits.
