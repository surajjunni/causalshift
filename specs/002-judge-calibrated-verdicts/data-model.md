# Phase 1 Data Model: Prediction-Powered Regression Verdicts (v2.0)

All entities are additive to the v1 trace store; v1 entities are unchanged.

## QualityDeltaObservation

A continuous baseline-vs-candidate quality difference for one trajectory.

| Field | Type | Notes |
|---|---|---|
| trajectory_id | str | FK to the v1 Trajectory |
| source | enum{judge, human} | judge: present for all evaluated trajectories; human: only for the audit sample |
| delta | float | candidate − baseline quality on a shared scale (negative = worse) |
| judge_id | str | judge identity (model+prompt+version) when source=judge; for provenance (FR of v2) |

- Validation: a trajectory in the evaluation set MUST have a judge observation; human observations
  exist only for sampled trajectories. Human and judge deltas use the same scale.

## HumanAuditSample

The design by which trajectories were chosen for human labeling.

| Field | Type | Notes |
|---|---|---|
| trajectory_id | str | FK; member of the audit sample |
| inclusion_prob | float (0,1] | sampling probability under the design (reflected in the interval) |
| stratum | str \| null | task category when traffic is stratified (e.g. retrieval/reasoning/tool-heavy) |

- Validation: inclusion_prob > 0 for every member; the per-stratum design is recorded so the interval
  can account for it (FR-003). A stratum present in evaluation traffic but absent here triggers
  conservative abstention (FR-006).

## JudgeInformativeness

A measured summary of how well the judge tracks true quality, driving power.

| Field | Type | Notes |
|---|---|---|
| metric | enum{residual_ratio, correlation} | residual_ratio = Var(human−judge)/Var(human); or judge–human correlation |
| value | float | measured on the audit sample |
| ci | (float, float) | interval on the metric |

## PPIEstimate

The prediction-powered mean-quality-delta estimate and its interval.

| Field | Type | Notes |
|---|---|---|
| mu_ppi | float | μ_PPI = judge mean over N + mean(human−judge) over n |
| ci | (float, float) | calibration-aware interval (sampling + judge-error uncertainty) |
| n_human | int | human-label count |
| n_eval | int | evaluated trajectory count |
| informativeness | JudgeInformativeness | reported with the estimate |
| sampling_var | float | interval contribution from the human-label sampling design |
| judge_var | float | interval contribution from judge/residual uncertainty |

- Validation: `mu_ppi` is never reported without `ci` (FR-002). `sampling_var` and `judge_var` are
  reported separately (FR-008); replay uncertainty (v1) is a third, separate figure — never summed into
  a single end-to-end bound.

## DeploymentVerdict

The PASS / FAIL / INCONCLUSIVE outcome against an acceptable-degradation margin.

| Field | Type | Notes |
|---|---|---|
| decision | enum{PASS, FAIL, INCONCLUSIVE} | INCONCLUSIVE → exit 2 (fail closed) |
| margin | float | acceptable mean degradation (deploy if μ ≥ −margin) |
| reason | str | e.g. "weak judge", "unlabeled stratum: tool-heavy", "thin labels", or the PASS/FAIL CI |
| estimate | PPIEstimate | the supporting estimate |
| abstention_rate | float | fraction of runs/strata abstained (reported, FR-005) |
| secondary_binary | object \| null | OPTIONAL Se/Sp (3-class pairwise) analysis, clearly labeled (FR-009) |

- State transitions: PASS if CI entirely above −margin; FAIL if entirely below; otherwise INCONCLUSIVE.
  INCONCLUSIVE also when informativeness is too low, labels insufficient, or a needed stratum is
  unlabeled.
