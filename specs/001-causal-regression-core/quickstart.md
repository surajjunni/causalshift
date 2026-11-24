# Quickstart & Validation: Causal Regression Core

Runnable scenarios that prove the feature works end to end. Implementation
details live in `tasks.md`; this is a validation guide. Contracts:
[trace-input](./contracts/trace-input.md),
[recompute-backend](./contracts/recompute-backend.md), [cli](./contracts/cli.md).

## Prerequisites

- Python 3.12, `uv` (dev) or `pip`.
- Optional for live recompute: a local Ollama with a small model. The core
  benchmark runs **without** it (seeded fixtures); live recompute is exercised
  separately.

## Setup

```bash
uv sync        # or: pip install -e .
```

## Scenario 1 — Sound verdict (P1, full re-execution)

Proves US1: a trustworthy regressed/not verdict with a confidence interval.

```bash
replaygate ingest benchmark/fixtures/demo_workflow.json
replaygate evaluate --workflow demo --intervention benchmark/fixtures/demo_intervention.json --mode full
```

Expected: a verdict stating regressed/not, magnitude + CI, and (for `full`
mode) no `reuse_exposure` line — full re-execution reuses nothing.

## Scenario 2 — Attribution (P2)

Proves US2: the responsible node is named.

Expected: on a case with a single planted fault, the report names the faulty
node with a confidence measure; on a no-fault case it reports no significant
regression.

## Scenario 3 — Selective replay + measured soundness (P3)

Proves US3: same verdict, fewer calls, reuse exposure reported.

```bash
replaygate evaluate --workflow demo --intervention benchmark/fixtures/demo_intervention.json --mode selective
```

Expected: same regressed/not verdict as Scenario 1, a lower `calls` count, and a
`reuse_exposure` headline (fraction of nodes reused; not a miss probability).
Any node whose reuse validity is uncertain shows `action = recomputed` with a
justification.

## Scenario 4 — The quality gate (primary)

Proves SC-001..005 with ground truth.

```bash
replaygate benchmark --json
```

Expected ComparisonReport fields, each checked against the spec targets:
detection_agreement ≥ 0.95, missed_regressions (false-negative) ≤ 0.05,
attribution_accuracy ≥ 0.80, and selective `call_count` ≤ 0.50 × full. These
are **measured and printed**, not assumed; a run that cannot meet the
false-negative bound fails the gate.

## Scenario 5 — Live, on a REAL text trace (Ollama)

Proves the real-world path: record a real agent run, then test a prompt change
against it with a live model + LLM judge.

```bash
python examples/live_agent.py --evaluate             # records via the seam AND evaluates, one script
# or, as separate CLI steps against the recorded trace:
replaygate ingest examples/real_trace.json --db /tmp/cs_real.db
replaygate evaluate --workflow real --intervention examples/bad_prompt.json \
    --db /tmp/cs_real.db --backend ollama --evaluator judge --mode selective --no-attribution
replaygate evaluate ... --mode full --no-attribution    # same verdict, more calls
```

The agent is instrumented with the `InstrumentedAgent` seam (declare deps once);
recording and replay share the same Ollama prompt-construction. Measured (llama3,
4 trajectories, v0.2 fair single-pass baseline): both modes agree the change
**regressed** quality (CI entirely below 0); **selective used 4 recompute calls
vs full's 12** (ratio 0.33), reusing the unaffected planner/retriever. (An
earlier "5 vs 75" came from a non-terminating repeated-pass full replay and
overstated the saving; v0.2's full re-execution is one pass per node.) The judge
is stochastic: a single score carries noise the trajectory bootstrap does not
fully capture (raise judge `k`). An inconclusive run exits 2 — never a silent pass.

## Out-of-contract check

```bash
replaygate ingest benchmark/fixtures/cyclic_workflow.json   # must error clearly, non-zero exit
```
