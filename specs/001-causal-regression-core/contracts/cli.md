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

**Exit codes (fail closed):** `0` = PASS (enough evidence, no regression); `1` =
FAIL (regression — CI below the margin); `2` = INCONCLUSIVE — the backend could
not recompute a node, OR there is insufficient evidence (fewer than the minimum
usable trajectories), OR the CI straddles the non-inferiority margin. An
inconclusive/insufficient run is NEVER a silent pass; CI blocks on 2 as well as 1.

### `causalshift benchmark [--json]`
Run the injected-fault benchmark: selective vs full across cases with known
ground truth. Emits the ComparisonReport (detection agreement, **missed
regressions** with a 95% CI, attribution accuracy, reuse exposure, calls,
tokens, latency). This is the primary quality gate.

### `causalshift diff --workflow <id> --intervention <spec> [--backend ...] [--evaluator ...] [--json]`
The one-command "is this change safe?" report (selective mode): plain-language
PASS / FAIL / INCONCLUSIVE + impact (magnitude + CI) + changed step + model
calls saved vs the fair baseline + reuse_exposure. Same 0/1/2 exit codes.

### Backends (`--backend`, on `evaluate` and `diff`)
`none` (default; recompute unavailable → affected nodes inconclusive), `ollama`
(local), `openai`, `anthropic`. Cloud backends read the API key from the
ENVIRONMENT (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`), never from the CLI and
never logged, and fail closed (missing key / error → inconclusive, exit 2).

## Rules

- Every verdict/report distinguishes measured values from assumptions.
- A verdict that relied on reuse MUST surface the reuse_exposure as the headline
  line, not a footnote (and must not mislabel it as a false-negative probability).
- `--json` output is stable and documented so results are scriptable/reproducible.
