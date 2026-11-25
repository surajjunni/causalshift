# Contract: CLI surface (v2.0, additive to v1)

v2 adds a judge-calibrated verdict path; v1 commands (`ingest`, `evaluate`, `diff`, `benchmark`) are
unchanged.

## `replaygate calibrate-verdict`

```text
replaygate calibrate-verdict \
  --workflow W \
  --intervention change.json \
  --judge <evaluator> \
  --human-labels labels.json \        # (human_delta, judge_delta) pairs for the audit sample
  --strata strata.json \              # optional: trajectory -> task category
  --budget 200 \                      # human-label budget if sampling is delegated
  --margin 0.05 \                     # acceptable mean degradation
  --min-labels 50 \
  --informativeness-floor 0.1
```

### Output (report)

```text
ReplayGate — judge-calibrated verdict [W]
  verdict:          INCONCLUSIVE — judge not informative enough
  mean quality Δ:   -0.03  (95% CI [-0.09, +0.03])   [PPI]
    sampling unc.:  ±0.04     judge unc.: ±0.03        (reported separately)
  judge informativeness: 0.22 (residual/outcome variance ratio; CI [0.14, 0.33])
  human labels:     120 / 500 evaluated   abstention: 1 stratum unlabeled (tool-heavy)
  replay (v1):      reuse exposure 0.6; benchmark FN rate <measured separately>
  exit:             2   (0 PASS / 1 FAIL / 2 INCONCLUSIVE)
```

### Guarantees (MUST)

- Exit codes: `0` PASS, `1` FAIL, `2` INCONCLUSIVE (fail closed on weak judge / thin labels /
  unlabeled stratum).
- The mean-Δ point estimate is always shown with its CI; sampling and judge uncertainty are shown
  separately from v1 replay uncertainty — no single end-to-end guarantee is printed (FR-008).
- An optional `--secondary-binary` flag prints the Se/Sp (3-class pairwise) analysis, clearly labeled
  as secondary (FR-009); it never changes the primary exit code.
