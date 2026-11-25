# Contract: Human-Audit Sampling

`replaygate.calibrate.sampling`

## Purpose

Choose which trajectories a human labels, by a known probability design, so the PPI residual
correction is unbiased and the interval can account for the design (FR-003). This is v2.0's primary
distribution-shift protection (FR-010).

## Inputs

- `trajectories: Sequence[TrajectoryRef]` — the evaluation set, each optionally carrying a `stratum`.
- `budget: int` — number of human labels to spend (e.g. 100–300).
- `strata: Sequence[str] | None` — task categories when traffic is heterogeneous.

## Output

- A `HumanAuditSample`: selected trajectory ids, each with `inclusion_prob` and `stratum`.

## Rules (MUST)

- When `strata` is provided, allocate the budget across strata (proportional or power-weighted) and
  record each item's `inclusion_prob` under that design.
- Every evaluation stratum with non-trivial weight MUST receive labels; a stratum that cannot be
  labeled within budget MUST be flagged so the verdict abstains for it (FR-006) rather than
  extrapolating.
- `inclusion_prob > 0` for every selected item; the design is persisted for the interval computation.
- The design MUST NOT systematically exclude hard/shifted strata — that is the bias failure mode the
  feasibility sims demonstrated (FINDINGS E1/C).

## Non-goals (v2.0)

- No online drift detector; no adaptive re-sampling loop. Representative sampling + conservative
  abstention is the v2.0 mechanism.
