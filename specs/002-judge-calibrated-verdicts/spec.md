# Feature Specification: Prediction-Powered Regression Verdicts (v2.0)

**Feature Branch**: `002-judge-calibrated-verdicts`

**Created**: 2026-11-24

**Status**: Draft (pivoted from binary judge calibration after feasibility simulation)

**Input**: User description: "ReplayGate v2 — make the regression verdict honest about the
unreliability of the quality evaluator, and label-efficient, so teams get actionable deployment
decisions from a small amount of human labeling plus many judge-scored trajectories."

## Context

v1 (`001-causal-regression-core`) answers "did quality regress under this change?" by applying a
quality evaluator (a *judge*) consistently to baseline and candidate outputs, and treats the judge's
score as ground truth. In practice that judge is an LLM-as-judge: biased, noisy, and unreliable under
distribution shift. v2 makes the verdict honest about that evaluator error without requiring a human
to label every trajectory.

**Design evolution (evidence-driven).** v2 was first scoped as binary judge calibration
(sensitivity/specificity correction of a better/worse decision). Feasibility simulations in
`specs/002-judge-calibrated-verdicts/feasibility/` (see `FINDINGS.md`) showed that approach is
*safe but low-power*: it abstains ~78–88% of the time **even with oracle per-category calibration**
(the abstention is intrinsic to the binary-prevalence estimand), and global calibration collapses to
near-0% interval coverage under calibration/evaluation distribution shift. The same simulations
showed a **continuous quality-delta estimator using prediction-powered inference (PPI)** reaching
≥70% actionable verdicts at 100–300 human labels with ~95% coverage *when the judge is informative*,
and failing safe (degrading to human-only power while keeping ~95% coverage) when it is not. v2 is
therefore pivoted to continuous-delta PPI as the primary design; binary/pairwise calibration becomes
an optional secondary analysis. These results are synthetic and directional; real-data validation is
the gating next step, not a larger speculative build.

## Clarifications

### Session 2026-11-24

- Q: Which judge output should v2 calibrate against first? → A: (superseded by the pivot) continuous
  quality delta is now primary; binary and pairwise are optional secondary analyses.
- Q: How should the measured evaluator error change the verdict? → A: Correct the estimate for judge
  bias (via PPI residual correction) AND report an interval that reflects judge + sampling
  uncertainty; never a point estimate presented as certain.
- Q: What should distribution-shift handling be based on? → A: Representative (stratified /
  probability-weighted) human-label sampling plus calibration-domain reporting; a full drift-detection
  service is deferred.
- Q: Default when the evaluator cannot support a trustworthy verdict? → A: Fail closed to INCONCLUSIVE
  (wider intervals / abstention), never a confident unsupported decision.
- Decision (feasibility sims, sim.py/sim2.py): primary estimand = continuous quality delta via PPI;
  stratified human-audit sampling with conservative handling when a stratum lacks human labels; three
  uncertainty sources (human evaluation, counterfactual/replay, sampling) reported separately; no
  single end-to-end 95% guarantee advertised until they are jointly validated.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Label-efficient, honest quality-delta verdict (Priority: P1)

An engineer wants to know how much a change degrades agent quality, without paying a human to label
every trajectory. They label a small random/stratified sample of trajectories, let the judge score
all of them, and ReplayGate returns a **prediction-powered estimate of the mean quality delta** with
a confidence interval that is honest about both judge error and sampling. The estimate corrects the
judge's bias using the human-labeled residuals, so it is far more precise than labeling the small
sample alone, yet never more confident than the evidence supports.

**Why this priority**: This is the core value and the pivot's whole point — actionable decisions at a
realistic human-label budget. It is independently testable on synthetic data with known true delta.

**Independent Test**: On synthetic trajectories with a known mean quality delta and a judge of known
informativeness, confirm the PPI estimate is approximately unbiased, its interval covers the true
delta at the nominal rate, and it yields a decisive PASS/FAIL more often than labeling the human
sample alone — at 100–300 labels.

**Acceptance Scenarios**:

1. **Given** a human-labeled sample plus judge scores over all trajectories and an informative judge,
   **When** the user runs a verdict, **Then** the PPI estimate's interval covers the true mean delta
   at the nominal rate and is materially narrower than the human-only interval at the same label
   count.
2. **Given** a biased, noisy (weakly informative) judge, **When** the user runs a verdict, **Then**
   the interval widens to remain honest (coverage preserved) and the verdict degrades toward
   INCONCLUSIVE — never a confident PASS/FAIL that the judge cannot support.

---

### User Story 2 - Representative human-audit sampling (Priority: P1)

Because PPI's bias correction is only as good as the human-labeled sample, ReplayGate draws that
sample by a known probability design — stratified across task categories (e.g. retrieval-heavy,
reasoning-heavy, tool-heavy) when the traffic has them — and accounts for the sampling design in the
interval. When a stratum present in the evaluation traffic has no human-label coverage, the system is
conservative rather than extrapolating.

**Why this priority**: Unrepresentative sampling silently biases the correction (the shift failure
mode from the sims). The sampling design is the primary shift protection in v2.0, so it ships with the
estimator. Independently testable.

**Independent Test**: Under heterogeneous traffic, compare representative/stratified sampling against a
sample that systematically excludes a hard stratum; confirm the stratified design keeps the interval
honest (coverage at nominal) while the biased sample's correction is detectably off, and that a
stratum with no labels triggers conservative abstention.

**Acceptance Scenarios**:

1. **Given** evaluation traffic spanning distinct task strata, **When** the user runs a verdict,
   **Then** human labels are sampled across strata by a known design and the interval accounts for
   that design.
2. **Given** a stratum present in evaluation traffic but absent from the human-labeled sample, **When**
   the user runs a verdict, **Then** the system handles it conservatively (abstains for that
   stratum/verdict) rather than silently extrapolating the correction.

---

### User Story 3 - Judge-informativeness-aware power (Priority: P2)

The usefulness of the verdict depends on how well the judge tracks true quality. ReplayGate measures
and reports the judge's informativeness, and lets it govern power: an informative judge yields tight
intervals and decisive verdicts; a weak judge yields wider intervals and more abstentions. A judge
that adds no information never produces a confident verdict.

**Why this priority**: It turns "trust the judge" into "trust the judge exactly as much as it has
earned," and gives the user a reason for an INCONCLUSIVE. Builds on US1/US2.

**Independent Test**: Sweep judge informativeness (noise relative to outcome spread); confirm reported
informativeness tracks the truth, interval width and abstention rate increase as informativeness
falls, and coverage is preserved throughout.

**Acceptance Scenarios**:

1. **Given** an informative judge, **When** the user runs a verdict, **Then** the reported
   informativeness is high and the actionable-verdict rate meets the target at the stated label budget.
2. **Given** an uninformative judge, **When** the user runs a verdict, **Then** the reported
   informativeness is low, the verdict is INCONCLUSIVE, and coverage is no worse than human-only.

---

### Edge Cases

- **Unrepresentative human sample**: a sample that excludes hard/shifted traffic biases the residual
  correction; mitigated by stratified/probability-weighted sampling (FR-003) and conservative handling
  of unlabeled strata (FR-006), never silently extrapolated.
- **Weak / uninformative judge**: PPI degrades to human-only power and stays honest (coverage
  preserved); it MUST NOT behave like the naive judge, whose bias collapses coverage.
- **Biased judge**: the residual correction removes systematic judge bias; an uncorrected (naive)
  path MUST NOT be presented as the verdict.
- **Stratum without human-label coverage**: conservative abstention for that stratum/verdict.
- **Three distinct uncertainties**: human-evaluation uncertainty, counterfactual-trajectory (replay)
  uncertainty, and sampling uncertainty are different problems; PPI corrects evaluator bias relative
  to the human sample but NOT replay error. A single end-to-end guarantee MUST NOT be claimed until
  they are jointly validated.
- **Insufficient human labels**: too few labels to bound the correction → INCONCLUSIVE, never a
  confident verdict.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST ingest, per evaluated trajectory, a continuous judge quality-delta
  observation, and for a sampled subset a continuous human quality-delta observation on the same scale
  (baseline-vs-candidate), reusing v1's trajectories unchanged.
- **FR-002**: System MUST produce the primary verdict as a prediction-powered estimate of the mean
  quality delta: the judge mean over all N trajectories, bias-corrected by the mean human−judge
  residual over the n labeled trajectories (μ_PPI = (1/N)Σ Δ̂_i + (1/n)Σ(Δ_j − Δ̂_j)), with a
  confidence interval that accounts for the human-label sampling design. The point estimate MUST NOT
  be reported without that interval.
- **FR-003**: System MUST draw the human-labeled subset by a known probability design, stratified
  across task categories when the traffic has distinct strata, and MUST account for the sampling
  design in the confidence interval. Representative sampling is a requirement, and its failure is the
  primary bias risk the design must surface.
- **FR-004**: The verdict MUST fail closed: when the judge is uninformative, the human labels are
  insufficient, or the sample cannot support the correction, the interval widens and the verdict
  becomes INCONCLUSIVE (exit 2) — never a confident PASS/FAIL the evidence does not support.
- **FR-005**: System MUST report, every run: the judge's measured informativeness (e.g. residual
  variance relative to outcome variance, or judge–human correlation), the estimated bias correction,
  the confidence interval, and the abstention rate.
- **FR-006**: When a task stratum present in the evaluation traffic lacks human-label coverage, the
  system MUST handle it conservatively (abstain for that stratum or the overall verdict) rather than
  extrapolating the correction into unlabeled regions.
- **FR-007**: v2 MUST keep v1's replay engine unchanged and be additive; it MUST NOT remove, weaken,
  or obscure any v1 output (reuse exposure, benchmarked false-negative rate).
- **FR-008**: System MUST distinguish three uncertainty sources in user-facing output — human quality
  evaluation, counterfactual-trajectory (selective-replay) error, and human-label sampling — and MUST
  NOT advertise a single end-to-end confidence guarantee until these are jointly validated. PPI
  corrects evaluator bias relative to the human sample only; it does not correct replay error.
- **FR-009**: Binary and pairwise judge calibration (sensitivity/specificity, with the ties and
  identifiability rules below) MAY be offered as an OPTIONAL SECONDARY analysis, clearly labeled, but
  MUST NOT be the primary verdict. If offered, pairwise ties require a three-class model, strictly
  binary requires an explicit positive class, calibration randomizes presentation order to measure
  position bias, and the correction MUST return INCONCLUSIVE when it is non-identifiable
  (Se + Sp − 1 near zero) rather than divide-by-near-zero or clamp-and-trust.
- **FR-010**: A full drift-detection service is OUT OF SCOPE for v2.0 and deferred. v2.0 protects
  against shift through representative stratified sampling (FR-003), explicit calibration-domain
  reporting, and conservative handling of unlabeled strata (FR-006).
- **FR-011**: System MUST provide a reproducible benchmark comparing the PPI verdict against (a)
  human-only evaluation at the same label budget, (b) the naive uncorrected judge, and (c) v1
  evaluation — on coverage, actionable-verdict rate, false deployment approval, and human-label
  requirement. The synthetic benchmark MUST run without any paid-API dependency, and the design MUST
  extend to real agent traces as the validation step.
- **FR-012**: Measured, not asserted: the PPI interval's empirical coverage MUST be validated by
  simulation (and by real-data holdout when available) before it gates a deployment decision, and the
  conditions under which power holds (judge informativeness, label budget) MUST be reported with the
  verdict, not assumed.

### Key Entities *(include if feature involves data)*

- **Quality-delta observation**: a continuous baseline-vs-candidate quality difference for one
  trajectory, from the judge (all trajectories) and/or a human (sampled subset), on a shared scale.
- **Human-audit sample**: the subset chosen for human labeling, with its sampling probabilities and
  task-stratum assignments (the design the interval must account for).
- **PPI estimate**: the bias-corrected mean quality delta, its confidence interval, the judge
  informativeness, and the abstention/INCONCLUSIVE status.
- **Judge informativeness**: a measured summary of how well the judge tracks true quality (residual
  variance vs outcome variance, or judge–human correlation) that governs power.
- **Deployment verdict**: PASS / FAIL / INCONCLUSIVE against a configured acceptable-degradation
  margin, with the three uncertainty sources reported separately.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** (central): At 100–300 human labels, the PPI verdict delivers substantially more
  actionable decisions than human-only evaluation while maintaining honest interval coverage and a low
  false deployment-approval rate — demonstrated first on the synthetic benchmark (already cleared in
  favorable conditions) and then validated on real agent traces.
- **SC-002**: With a biased, noisy judge, the PPI interval maintains approximately nominal coverage
  (~95%) where the naive uncorrected judge's coverage collapses.
- **SC-003**: With an informative judge, the actionable-verdict rate reaches at least 70% at a label
  budget of ≤300; with a weak judge, coverage is no worse than human-only and no confident unsupported
  verdict is issued.
- **SC-004**: Every verdict reports judge informativeness, the estimated correction, the confidence
  interval, and the abstention rate.
- **SC-005**: A task stratum present in evaluation traffic but absent from the human-labeled sample
  triggers conservative abstention, never silent extrapolation.
- **SC-006**: v2 leaves v1's replay engine and outputs unchanged (additive).
- **SC-007**: No single end-to-end confidence guarantee is reported until human-evaluation,
  counterfactual-replay, and sampling uncertainties are jointly validated; until then the three are
  reported separately.

## Assumptions

- PPI's power is contingent on judge informativeness (noise relative to outcome spread) and MUST be
  reported, not assumed; an uninformative judge yields human-only-level power, not failure.
- Human-label sampling is representative (stratified or probability-weighted for heterogeneous
  traffic); the failure of this assumption is the primary bias risk and is guarded by FR-003/FR-006.
- A continuous quality score is definable per trajectory on a shared human/judge scale; defining that
  score is upstream of this feature (as in v1).
- The feasibility results are synthetic and directional; real-data validation on agent traces is the
  gating next step before any end-to-end deployment-safety claim.
- The statistical method (prediction-powered inference) is established prior work and is NOT claimed
  as novel; ReplayGate's contribution is applying it to agent-replay deployment decisions and, as a
  longer-term research contribution, jointly modeling evaluator and selective-replay uncertainty
  (Constitution Principle V).
- v2.0 is the smallest feature that can reproduce the simulation's result on real trajectories; it
  keeps v1 unchanged and defers the drift-detection service.
