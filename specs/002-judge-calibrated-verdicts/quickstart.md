# Quickstart & Validation: Prediction-Powered Regression Verdicts (v2.0)

This guide proves v2.0 works end to end. It references the contracts
([ppi-estimator](./contracts/ppi-estimator.md), [human-audit-sampling](./contracts/human-audit-sampling.md),
[cli](./contracts/cli.md)) and the data model rather than duplicating them.

## Prerequisites

- v1 installed (`uv pip install -e ".[dev]"`).
- A v1 workflow with recorded trajectories and a proposed intervention.
- A quality evaluator (judge) and a small human-labeled subset of trajectories.

## The feasibility evidence (already runnable)

The design is backed by the simulations in `feasibility/`; run them to reproduce the result the
benchmark must preserve:

```bash
python3 specs/002-judge-calibrated-verdicts/feasibility/sim.py    # binary: safe but low-power / shift-fragile
python3 specs/002-judge-calibrated-verdicts/feasibility/sim2.py   # stratified + PPI: the pivot evidence
```

## Validation scenarios (what the implementation must satisfy)

1. **Label-efficient honest verdict (SC-001, SC-003).**
   Run `replaygate calibrate-verdict` with 100–300 human labels on trajectories with a known planted
   mean Δ and an informative judge. Expect: PPI CI covers the true Δ at ~95%, and the actionable
   (PASS/FAIL) rate exceeds human-only at the same label count.

2. **Honest under a weak judge (SC-002).**
   Use a biased, noisy judge. Expect: coverage stays ~95% (naive judge would collapse), the interval
   widens, and the verdict trends INCONCLUSIVE — never a confident unsupported PASS/FAIL.

3. **Conservative on unlabeled strata (SC-005).**
   Provide evaluation traffic with a stratum (e.g. tool-heavy) absent from the human sample. Expect:
   the verdict abstains for that stratum and names it as the reason; no silent extrapolation.

4. **Reporting completeness (SC-004).**
   Every run prints judge informativeness (with CI), the bias correction, the PPI CI with sampling and
   judge uncertainty shown separately, and the abstention rate.

5. **Additivity (SC-006).**
   v1 commands (`evaluate`, `diff`, `benchmark`) produce identical output to before; v2 is purely
   additive.

6. **Separated uncertainties (SC-007).**
   The report never prints a single end-to-end 95% guarantee; human-eval, replay, and sampling
   uncertainty appear as distinct figures.

## Gate

`benchmark/ppi/coverage.py` must show empirical CI coverage ≈ nominal across the informativeness ×
label-budget × stratum grid before the estimate may gate a real decision (FR-012). The central open
validation (SC-001) is to reproduce scenarios 1–2 on **real agent traces**, not only synthetic ones.
