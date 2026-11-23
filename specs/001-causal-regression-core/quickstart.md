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
causalshift ingest benchmark/fixtures/demo_workflow.json
causalshift evaluate --workflow demo --intervention benchmark/fixtures/demo_intervention.json --mode full
```

Expected: a verdict stating regressed/not, magnitude + CI, and (for `full`
mode) a `false_negative_risk` of 0 — nothing was reused.

## Scenario 2 — Attribution (P2)

Proves US2: the responsible node is named.

Expected: on a case with a single planted fault, the report names the faulty
node with a confidence measure; on a no-fault case it reports no significant
regression.

## Scenario 3 — Selective replay + measured soundness (P3)

Proves US3: same verdict, fewer calls, false-negative risk reported.

```bash
causalshift evaluate --workflow demo --intervention benchmark/fixtures/demo_intervention.json --mode selective
```

Expected: same regressed/not verdict as Scenario 1, a lower `calls` count, and
a non-null measured `false_negative_risk`. Any node whose reuse validity is
uncertain shows `action = recomputed` with a justification.

## Scenario 4 — The quality gate (primary)

Proves SC-001..005 with ground truth.

```bash
causalshift benchmark --json
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
python examples/record_trace.py                      # runs a 3-step agent on Ollama → examples/real_trace.json
causalshift ingest examples/real_trace.json --db /tmp/cs_real.db
causalshift evaluate --workflow real --intervention examples/bad_prompt.json \
    --db /tmp/cs_real.db --backend ollama --evaluator judge --mode selective --no-attribution
causalshift evaluate ... --mode full --no-attribution    # same verdict, far more calls
```

Observed (llama3, 5 trajectories): both modes agree the change **regressed**
quality (CI entirely below 0); **selective used 5 recompute calls vs full's 75**
(reusing the unaffected planner/retriever), and reported the reuse false-negative
risk as the headline. The judge is stochastic — a single score carries noise the
trajectory bootstrap does not fully capture (raise judge `k` to reduce it).

## Out-of-contract check

```bash
causalshift ingest benchmark/fixtures/cyclic_workflow.json   # must error clearly, non-zero exit
```
