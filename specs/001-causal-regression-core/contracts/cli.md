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
attribution, and — always — the measured `false_negative_risk` for any reuse.
`--mode full` is the sound baseline; `--mode selective` is dependency-aware
replay. Exit code is non-zero when a regression is detected (CI-based), so it
can gate CI.

### `causalshift benchmark [--json]`
Run the injected-fault benchmark: selective vs full across cases with known
ground truth. Emits the ComparisonReport (detection agreement, **missed
regressions**, attribution accuracy, calls, tokens, latency). This is the
primary quality gate.

## Rules

- Every verdict/report distinguishes measured values from assumptions.
- A verdict that relied on reuse MUST surface the false-negative risk as the
  headline line, not a footnote.
- `--json` output is stable and documented so results are scriptable/reproducible.
