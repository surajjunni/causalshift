# Phase 0 Research: Prediction-Powered Regression Verdicts (v2.0)

Unlike a greenfield feature, v2.0's key unknowns were resolved empirically by the feasibility
simulations in `feasibility/` (`sim.py`, `sim2.py`, `FINDINGS.md`). This document consolidates those
decisions. No open NEEDS CLARIFICATION remain for the v2.0 scope.

## D1 — Primary estimand: continuous quality delta (not binary prevalence)

- **Decision**: The primary verdict estimates the mean continuous quality delta, not the binary/pairwise
  regression prevalence.
- **Rationale**: In `sim.py`/`sim2.py`, the binary-prevalence estimand abstains ~78–88% of the time
  **even with an oracle calibration** — the low power is intrinsic to the estimand, not an estimation
  artifact. The continuous-delta estimator reaches 50–100% actionable at the same label budgets.
- **Alternatives considered**: Binary sensitivity/specificity calibration (demoted to optional
  secondary, FR-009); pairwise preference (secondary). Kept because some judges only emit a decision.

## D2 — Correction method: prediction-powered inference (PPI)

- **Decision**: Correct the judge using human-labeled residuals via PPI:
  `μ_PPI = (1/N)Σ Δ̂_i + (1/n)Σ (Δ_j − Δ̂_j)`, with a calibration-aware interval.
- **Rationale**: PPI needs no global Se/Sp profile; it debiases the judge mean over the large
  evaluation set using the small human sample. In `sim2.py` it held ~95% coverage even for biased,
  noisy judges where the naive judge's coverage collapsed to 0%, and recovered human-only power when
  the judge was uninformative. PPI is established prior work (ICML 2026 "noisy LLM-as-judge" line), so
  the contribution is correct application, not a new estimator.
- **Alternatives considered**: naive judge mean (fails: confidently wrong under bias); human-only mean
  (honest but low power); misclassification correction on a binarized decision (D1).

## D3 — Shift handling: representative sampling, not a drift service (v2.0)

- **Decision**: Protect against distribution shift with stratified / probability-weighted human-audit
  sampling and conservative handling of unlabeled strata; defer a full drift-detection service.
- **Rationale**: In `sim2.py`, global calibration under a cal≠eval mixture collapsed coverage to ~0%.
  Stratified calibration restored coverage (~94–95%) but the gain comes from sampling the right strata,
  not from a separate detector. The simplest sufficient protection is a correct sampling design plus
  abstention where labels are missing (FR-003, FR-006).
- **Alternatives considered**: feature-based drift detector as primary protection (deferred —
  "a safeguard, not a proof"); global calibration (rejected — collapses under shift).

## D4 — Fail-closed and separated uncertainties

- **Decision**: Weak judge / thin labels / unlabeled stratum → wider interval → INCONCLUSIVE (exit 2).
  Report human-evaluation, counterfactual-replay, and sampling uncertainty separately; do not advertise
  a single end-to-end guarantee.
- **Rationale**: Constitution Principle I; and PPI corrects evaluator bias relative to the human sample
  only — it does not correct selective-replay error, which is a distinct uncertainty (v1). Conflating
  them would overstate confidence.
- **Alternatives considered**: a single combined 95% bound (rejected until the replay/judge error
  correlation is benchmarked, FR-008).

## D5 — Judge informativeness governs power, and is reported

- **Decision**: Measure and report judge informativeness (residual variance vs outcome variance, or
  judge–human correlation); let it drive interval width and abstention.
- **Rationale**: `sim2.py` showed PPI's power gain is entirely contingent on informativeness (noise ≪
  outcome spread → large gain; noise ≈ spread → human-only power). Reporting it tells the user *why* a
  verdict is (in)conclusive and prevents over-trust.
- **Alternatives considered**: assume a fixed informativeness (rejected — not measured, not honest).

## D6 — Libraries and validation

- **Decision**: `numpy` + `scipy` only; PPI interval coverage validated by simulation (and real-trace
  holdout when available) before it may gate a decision.
- **Rationale**: the estimator is a few vectorized operations; the simulations already run in seconds.
  Coverage validation is mandated by Principle III and is the benchmark's job.
- **Alternatives considered**: a PPI library dependency (unnecessary for the basic estimator; revisit
  only if stratified/power-tuned PPI variants are added).
