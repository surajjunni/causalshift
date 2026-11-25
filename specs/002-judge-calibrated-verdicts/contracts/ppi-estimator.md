# Contract: PPI Estimator & Verdict

`replaygate.calibrate.ppi`

## Inputs

- `judge_deltas: Sequence[float]` — judge quality delta for all N evaluated trajectories.
- `human_pairs: Sequence[tuple[float, float]]` — (human_delta, judge_delta) for the n labeled
  trajectories (n ≤ N).
- `inclusion_probs: Sequence[float] | None` — per-labeled-item sampling probabilities (design); None
  means simple random.
- `margin: float` — acceptable mean degradation; deploy if mean delta ≥ −margin.
- `min_labels: int` — below this the verdict fails closed.
- `informativeness_floor: float` — below this the judge is treated as uninformative (fail closed).

## Output: `PPIEstimate` + `DeploymentVerdict`

- `mu_ppi = mean(judge_deltas) + weighted_mean(human_delta − judge_delta over labeled)`
  (Horvitz–Thompson weighting by `inclusion_probs` when provided).
- `ci` — calibration-aware: `var = judge_var + sampling_var`, where `sampling_var` is the variance of
  the residual correction under the sampling design and `judge_var` the N-sample judge-mean variance.
- `decision`:
  - `PASS` iff `ci_low > −margin`
  - `FAIL` iff `ci_high < −margin`
  - `INCONCLUSIVE` otherwise, OR `n < min_labels`, OR `informativeness < informativeness_floor`, OR a
    required stratum is unlabeled (see `human-audit-sampling.md`).

## Guarantees (MUST)

- `mu_ppi` is never returned without `ci` (FR-002).
- `sampling_var` and `judge_var` are returned separately and are NOT summed with v1 replay uncertainty
  into a single end-to-end bound (FR-008).
- INCONCLUSIVE maps to CLI exit code 2 (fail closed, FR-004).
- A zero/degraded judge signal degrades to human-only inference (coverage preserved), never to a naive
  confident verdict.

## Validation

- `benchmark/ppi/coverage.py` MUST show empirical CI coverage ≈ nominal across the informativeness ×
  label-budget × stratum grid before the estimate is used as a gate (FR-012, Principle III).
