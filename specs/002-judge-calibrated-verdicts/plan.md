# Implementation Plan: Prediction-Powered Regression Verdicts (v2.0)

**Branch**: `002-judge-calibrated-verdicts` | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-judge-calibrated-verdicts/spec.md`

## Summary

ReplayGate v2.0 makes the regression verdict honest about evaluator (LLM-judge) error, label-
efficiently. It keeps v1's replay engine unchanged and adds a calibration layer: a human-audit
sample (stratified / probability-weighted) is labeled, the judge scores all trajectories, and a
**prediction-powered inference (PPI)** estimator reports the mean quality delta with a confidence
interval that accounts for judge error and the sampling design. The verdict fails closed — a weak
judge, thin labels, or an unlabeled stratum yields wider intervals / INCONCLUSIVE, never a confident
unsupported decision. Judge informativeness, the bias correction, the interval, and the abstention
rate are reported every run. Binary/pairwise sensitivity-specificity calibration is an optional,
clearly-labeled secondary analysis. A full drift-detection service and a combined end-to-end
(replay + judge + sampling) guarantee are explicitly out of scope for v2.0.

This scope follows directly from the feasibility simulations in `feasibility/` (see `FINDINGS.md`):
binary calibration is safe but low-power and collapses under distribution shift; continuous-delta PPI
reaches ≥70% actionable at 100–300 labels with ~95% coverage when the judge is informative, and fails
safe otherwise.

## Technical Context

**Language/Version**: Python 3.12 (same as v1).

**Primary Dependencies**: `numpy` and `scipy` for the PPI estimator and calibration-aware intervals;
reuse v1's `store/` and `evaluate/`. No web/infra frameworks; no paid-API dependency for the core
benchmark.

**Storage**: reuse v1's SQLite trace store; add a human-label observation table (per-trajectory
continuous human quality delta) and a sample-design record (sampling probabilities, stratum).

**Testing**: `pytest` for deterministic unit/integration tests; the **PPI benchmark** (the `feasibility/`
simulations promoted into `benchmark/ppi/`) is the primary gate — coverage and actionable-rate are
validated by simulation before the estimate may gate a decision.

**Target Platform**: local CLI / library (macOS, Linux). No server.

**Project Type**: single Python package — additive extension of the v1 `replaygate` package.

**Performance Goals**: at a 100–300 human-label budget, the PPI verdict yields a materially higher
actionable-verdict rate than human-only evaluation while holding ~95% interval coverage and a low
false deployment-approval rate (SC-001/002/003).

**Constraints**: fail-closed is gating (weak judge / thin labels / unlabeled stratum → INCONCLUSIVE);
PPI power is contingent on and MUST report judge informativeness; human sampling MUST be representative
(stratified/probability-weighted) with the design reflected in the interval; the three uncertainty
sources (human eval, counterfactual/replay, sampling) stay separate — no single end-to-end guarantee.

**Scale/Scope**: tens–hundreds of evaluated trajectories per run; a human-labeled subset of ~100–300;
synthetic benchmark first, real agent traces as the validation step.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Soundness Over Savings | No point estimate without an interval; fail-closed on weak judge / thin labels / unlabeled stratum; no end-to-end guarantee until joint uncertainty validated; false-approval measured on the benchmark. | PASS (enforced in `calibrate/` + `report/`; CLI exit 2 on INCONCLUSIVE) |
| II. Reuse/Recompute/Quantify | v2 is additive; v1's reuse/recompute/soundness ledger is untouched, and v2 adds a second quantified error source (judge) reported separately. | PASS |
| III. Measured, Not Asserted | PPI interval coverage validated by simulation before gating; judge informativeness and correction reported as measured, with conditions for power stated. | PASS (enforced in `benchmark/ppi/` + `report/`) |
| IV. Scope Honesty | v2.0 defers the drift service and the combined guarantee; binary is secondary; synthetic evidence is labeled directional; real-data validation pending. | PASS |
| V. Complementary Positioning | PPI is established prior work (cited); the contribution is applying it to agent-replay deployment decisions and, longer-term, jointly modeling evaluator + selective-replay uncertainty. | PASS (docs task) |

No violations → Complexity Tracking omitted.

## Project Structure

### Documentation (this feature)

```text
specs/002-judge-calibrated-verdicts/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── ppi-estimator.md       # PPI estimate + calibration-aware CI + fail-closed rules
│   ├── human-audit-sampling.md# stratified/probability-weighted sample design contract
│   └── cli.md                 # v2 CLI surface (calibrate / verdict, additive to v1)
├── feasibility/         # already present: sim.py, sim2.py, FINDINGS.md (the evidence base)
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/replaygate/
├── calibrate/        # NEW v2 layer
│   ├── sampling.py       # human-audit sample design: stratified / probability-weighted; records probs + stratum
│   ├── ppi.py            # prediction-powered estimator + calibration-aware confidence interval
│   ├── informativeness.py# judge-informativeness metric (residual vs outcome variance / correlation)
│   └── binary.py         # OPTIONAL secondary: Se/Sp (and 3-class pairwise) correction, identifiability-guarded
├── evaluate/         # EXTENDED: emit the continuous quality-delta verdict via calibrate/ppi; keep v1 path
├── report/           # EXTENDED: report informativeness, correction, CI, abstention; three uncertainty sources separate
├── store/            # EXTENDED: human-label observation table + sample-design record (additive schema)
└── cli.py            # EXTENDED: `replaygate calibrate` / verdict flags; exit 2 on INCONCLUSIVE

benchmark/
└── ppi/              # NEW: PPI benchmark promoted from specs/002/feasibility
    ├── synthetic.py      # human-only vs naive-judge vs PPI; coverage + actionable + false-approval
    ├── coverage.py       # CI coverage validation across informativeness / label budget / strata
    └── real_traces.py    # adapter + harness for the real-trace validation step (SC-001)

tests/
├── unit/             # ppi estimator, sampling design, informativeness, binary identifiability guard, fail-closed
└── integration/      # end-to-end verdict on seeded trajectories; abstention on unlabeled stratum
```

**Structure Decision**: Additive extension of the v1 `replaygate` package. All new logic lives in a
dedicated `calibrate/` module so the judge-error layer is isolated from, and never entangled with,
v1's replay/soundness code (mirroring how v1 isolates `soundness/`). `evaluate/`, `report/`, `store/`,
and `cli.py` gain additive v2 paths without changing v1 behavior. The feasibility simulations graduate
into `benchmark/ppi/` as the quality gate.
