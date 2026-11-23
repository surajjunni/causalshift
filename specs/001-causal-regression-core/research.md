# Phase 0 Research: Causal Regression Core

The Technical Context carried no open `NEEDS CLARIFICATION` items; the decisions
below record the rationale and the alternatives weighed, per the constitution's
"measured, not asserted" obligation (these are design choices, validated later
by the benchmark — not results).

## Decision: SQLite trace store (stdlib), DuckDB deferred

- **Decision**: Normalize instrumented trajectories into SQLite via stdlib
  `sqlite3`; keep an ordinal-preserving schema so a later DuckDB swap needs no
  logic change.
- **Rationale**: Zero install, offline, reproducible; proven on the prototype
  corpus. The deployment-testing workload is modest (tens–hundreds of
  trajectories), not analytical-at-scale.
- **Alternatives**: DuckDB (better for large sweeps — deferred until needed);
  ClickHouse/Postgres (Tracely's stack — rejected: heavy infra violates the
  simple-tool positioning); JSON files (rejected: not queryable for dependency
  closure).

## Decision: Dependency DAG via networkx; causal closure = reachable set

- **Decision**: Model declared step dependencies as a directed graph; the
  "causally-affected set" of an intervention at node N is N plus its
  descendants reachable through dependency edges.
- **Rationale**: This is the soundness backbone — only nodes outside the
  affected set are *candidates* for reuse. networkx gives reachability/toposort
  for free and is a light dependency.
- **Alternatives**: hand-rolled graph (rejected: reinventing reachability);
  implicit ordering by step index (rejected: unsound — ignores real data flow).

## Decision: Validity predicate gates reuse; fail toward recompute

- **Decision**: A recorded step's output may be reused only if (a) it is outside
  the causally-affected set AND (b) a validity predicate confirms its relevant
  inputs and environmental assumptions are unchanged. If the predicate cannot
  confirm validity, recompute (escalate).
- **Rationale**: Directly implements Constitution Principles I & II. The
  predicate is the single point where soundness is enforced, so it is isolated
  and auditable.
- **Alternatives**: "reuse everything after the cut-point unless proven changed"
  (rejected — this is the unsound conservative inverse that silently misses
  regressions; it is exactly the prototype weakness CausalShift fixes).

## Decision: Full re-execution baseline as the correctness oracle

- **Decision**: Implement full re-execution (recompute the whole affected
  trajectory, no reuse) first; it is sound by construction and the oracle the
  benchmark measures selective replay against.
- **Rationale**: Gives a trustworthy P1 verdict before any efficiency work, and
  a ground-truth-independent cross-check: selective and full must agree.
- **Alternatives**: ship selective-only (rejected — nothing to validate against;
  violates priority order).

## Decision: Bootstrap confidence intervals for population effect

- **Decision**: Estimate regression magnitude and its CI by bootstrap
  resampling over trajectories; report "no significant regression" when the CI
  crosses zero.
- **Rationale**: Distribution-free, simple, separates real effect from sampling
  noise (FR-007, SC-005); matches the prototype's bootstrap approach.
- **Alternatives**: parametric t-tests (rejected — distributional assumptions on
  quality scores unwarranted); point estimates only (rejected — violates
  measured-with-uncertainty).

## Decision: Attribution by causal contribution, single-fault first

- **Decision**: Attribute a regression by comparing per-node causal
  contribution (effect when that node's change is included vs isolated);
  target single-fault accuracy first, then credit-splitting for interactions.
- **Rationale**: Matches spec priority (P2 before interaction handling) and the
  SC-004 single-fault target; stays an attribution-of-a-change, not CAR-style
  general single-run attribution (non-goal).
- **Alternatives**: LLM-judge "which step looks worst" (rejected — correlational,
  low accuracy per CAR's ~14% finding).

## Decision: Pluggable recompute backend; local Ollama default; graceful fallback

- **Decision**: A `RecomputeBackend` interface; default a thin stdlib-`urllib`
  client to a local model (Ollama); on any failure or absence it returns "cannot
  recompute," which escalates per the validity rules rather than crashing.
- **Rationale**: Tier-1 recompute is live-only and must degrade cleanly
  (constitution); no paid-API dependency for the core benchmark.
- **Alternatives**: hard dependency on a specific SDK (rejected — couples the
  tool to one provider and breaks offline runs).

## Decision: Injected-fault benchmark as the primary gate

- **Decision**: Generate synthetic DAG trajectories with planted faults (known
  faulty node, known whether it regresses), including **missing-dependency-edge**
  cases, so false-negative rate and attribution accuracy are measurable.
- **Rationale**: The only way to satisfy "measured, not asserted" for SC-001..005
  and to measure the headline false-negative metric honestly.
- **Alternatives**: real-trace-only evaluation (rejected — no ground truth, can't
  measure missed regressions).
