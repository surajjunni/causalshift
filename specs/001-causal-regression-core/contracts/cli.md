# Contract: CLI

The command surface of the `causalshift` tool. Text in/args → stdout;
machine-readable report via `--json`; errors → stderr, non-zero exit.

## Commands

### `causalshift ingest <input.json> [--db PATH]`
Validate and load instrumented trajectories (see
[trace-input.md](./trace-input.md)) into the trace store. Rejects cyclic/out-of-
contract inputs with a clear message and non-zero exit.

### `causalshift evaluate --workflow <id> --intervention <spec> [--mode full|selective] [--backend ...] [--json]`
Run the regression evaluation for an intervention across the workflow's
trajectories. Emits a RegressionVerdict: regressed (yes/no), magnitude + CI,
attribution, and — for any reuse — the `reuse_exposure` headline (fraction of
nodes reused; an exposure measure, not a miss probability). `--mode full` is the
sound baseline; `--mode selective` is dependency-aware replay.

**Exit codes (fail closed):** `0` = conclusive, no regression; `1` = regression
detected (CI entirely below zero); `2` = inconclusive (the backend could not
recompute a node) — an inconclusive run is NEVER a silent pass, so CI blocks on
exit 2 as well as 1.

### `causalshift benchmark [--json]`
Run the injected-fault benchmark: selective vs full across cases with known
ground truth. Emits the ComparisonReport (detection agreement, **missed
regressions**, attribution accuracy, calls, tokens, latency). This is the
primary quality gate.

## Rules

- Every verdict/report distinguishes measured values from assumptions.
- A verdict that relied on reuse MUST surface the reuse_exposure as the headline
  line, not a footnote (and must not mislabel it as a false-negative probability).
- `--json` output is stable and documented so results are scriptable/reproducible.
