---
description: "Task list for Causal Regression Core"
---

# Tasks: Causal Regression Core

**Input**: Design documents from `specs/001-causal-regression-core/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included selectively for soundness-critical and contract-critical
behavior (per the constitution), not as blanket TDD. The injected-fault
benchmark (Phase 6) is the primary quality gate.

**Constitution gates carried into tasks**: no state reuse without a validity
proof (fail toward recompute); every claim validated against ground truth with
uncertainty; DAG-only (reject cyclic); honest positioning.

## Phase 1: Setup

- [X] T001 Scaffold the pip-installable package: `pyproject.toml` (name `causalshift`, Python 3.12, deps `networkx`, `numpy`; `causalshift` console entry point → `causalshift.cli:main`), `src/causalshift/__init__.py`, and empty component packages (`store`, `graph`, `intervene`, `backends`, `replay`, `soundness`, `evaluate`, `attribute`, `report`) per plan.md Project Structure
- [X] T002 [P] Add dev tooling: `pytest` config, a global random seed helper in `src/causalshift/_seed.py`, and `tests/unit/`, `tests/integration/` dirs with `conftest.py`
- [X] T003 [P] Add a stub `src/causalshift/cli.py` with `main()` and an argparse skeleton for `ingest` / `evaluate` / `benchmark` (no behavior yet) per contracts/cli.md

## Phase 2: Foundational (blocking — must complete before any user story)

- [X] T004 Implement core entities in `src/causalshift/models.py`: Trajectory, Step, DependencyEdge, Intervention, ReplayDecision, ReplayResult, RegressionVerdict, BenchmarkCase, ComparisonReport — fields per data-model.md. Enforce `Step.input_fingerprint` is mandatory (data-model.md `Step.input_fingerprint`) and `ReplayDecision.action`∈{reused,recomputed} with the reuse rule `in_affected_set=false ∧ validity_checked=valid` (data-model.md `ReplayDecision`)
- [X] T005 Implement SQLite trace store in `src/causalshift/store/db.py`: normalized, ordinal-preserving schema + ingest/hydrate for Trajectory/Step/DependencyEdge (data-model.md), DuckDB-swappable
- [X] T006 Implement trace-input validation in `src/causalshift/store/validate.py` per contracts/trace-input.md: reject cyclic graphs, reject steps referencing undeclared nodes, require `input_fingerprint` on every step (data-model.md `Step.input_fingerprint`); raise a clear error with non-zero-exit semantics
- [X] T007 [P] Test foundational validation in `tests/unit/test_validate.py`: cyclic graph rejected; missing `input_fingerprint` rejected; undeclared node rejected; valid DAG accepted
- [X] T008 Implement dependency-graph model in `src/causalshift/graph/dag.py` (networkx): build from edges, toposort, and `affected_set(intervention)` = targeted nodes ∪ their descendants (research.md: causal closure)
- [X] T009 [P] Test causal closure in `tests/unit/test_graph.py`: affected set correct for leaf, root, and mid-DAG interventions; disconnected nodes excluded
- [X] T010 Define the recompute backend contract in `src/causalshift/backends/base.py` per contracts/recompute-backend.md: `RecomputeBackend` interface, `Produced`/`Unavailable` outcomes, and `UnavailableBackend` (always `Unavailable`)
- [X] T011 [P] Implement local Ollama backend in `src/causalshift/backends/ollama.py`: stdlib `urllib`, `max_calls` budget, returns `Unavailable` on any error/absence/budget (never raises); `ollama_available()` probe

**Checkpoint**: trace store, validation, DAG closure, and backend seam exist and are unit-tested.

## Phase 3: User Story 1 — Trustworthy go/no-go verdict (P1) 🎯 MVP

**Goal**: Given trajectories + an intervention, produce a sound population-level
regressed/not verdict with a confidence interval, via full re-execution (no reuse).
**Independent test**: On an injected-fault fixture, the verdict and magnitude CI
match the planted effect; a no-fault fixture yields "no significant regression."

- [X] T012 [US1] Implement the intervention engine in `src/causalshift/intervene/apply.py`: substitute model/prompt at named nodes (Intervention per data-model.md); validate targets exist in the graph
- [X] T013 [US1] Implement a pluggable quality evaluator interface + a default in `src/causalshift/evaluate/quality.py`: scores baseline vs candidate outputs identically (spec Assumptions); evaluator is injected, not hard-coded
- [X] T014 [US1] Implement full re-execution replay in `src/causalshift/replay/full.py`: recompute every affected node via the backend (no reuse); if the backend returns `Unavailable` for an affected node, mark that trajectory's result **inconclusive** (never "safe") per contracts/recompute-backend.md
- [X] T015 [US1] Implement the population evaluator with bootstrap CIs in `src/causalshift/evaluate/population.py`: aggregate per-trajectory quality deltas across many trajectories; `regressed` iff the CI excludes zero (research.md; FR-007, SC-005)
- [X] T016 [US1] Assemble RegressionVerdict + reporting in `src/causalshift/report/verdict.py`: regressed/magnitude/CI, no `reuse_exposure` for full mode (nothing reused), and `measured_vs_assumed` tags on every figure (FR-012)
- [X] T017 [US1] Wire `causalshift ingest <input.json>` and `causalshift evaluate --workflow --intervention --mode full [--json]` in `src/causalshift/cli.py` per contracts/cli.md; non-zero exit when a regression is detected
- [X] T018 [P] [US1] Integration test in `tests/integration/test_us1_full_verdict.py`: planted-fault fixture → regressed verdict with CI; no-fault fixture → no significant regression (false-alarm within SC-005)

**Checkpoint**: MVP — a usable, sound verdict from real trajectories via full re-execution.

## Phase 4: User Story 2 — Localize the responsible decision (P2)

**Goal**: Attribute a detected regression to the responsible node(s).
**Independent test**: On single-fault benchmark cases, attribution names the correct node ≥ SC-004.

- [X] T019 [US2] Implement regression attribution in `src/causalshift/attribute/causal.py`: per-node causal contribution (effect with a node's change included vs isolated), ranked, with a confidence measure (research.md; FR-008). Single-fault first; split credit across interacting nodes
- [X] T020 [US2] Extend RegressionVerdict + report in `src/causalshift/report/verdict.py` to carry ranked attribution; surface it in `causalshift evaluate` output (contracts/cli.md)
- [X] T021 [P] [US2] Integration test in `tests/integration/test_us2_attribution.py`: single planted fault → correct node named with confidence; interacting faults → credit split, not all-or-nothing

**Checkpoint**: verdict now says *which* decision regressed.

## Phase 5: User Story 3 — Selective replay + measured soundness (P3)

**Goal**: Reach the same verdict with fewer model calls via dependency-aware
reuse, reporting the measured false-negative risk.
**Independent test**: Selective agrees with full on the benchmark at ≥ SC-001,
≤ SC-003 of the calls, with false-negative rate measured and ≤ SC-002.

- [X] T022 [US3] Implement the validity predicate in `src/causalshift/replay/validity.py`: a recorded step is reusable ONLY if its `input_fingerprint` is unchanged under the intervention; any uncertainty ⇒ not reusable (fail toward recompute) (research.md; FR-004/FR-005; data-model.md `ReplayDecision`)
- [X] T023 [US3] Implement DYNAMIC selective replay in `src/causalshift/replay/engine.py`: recompute a node iff it is an intervention target OR its declared inputs actually changed (validity fails); reuse (prune) unchanged descendants; record a ReplayDecision with justification for every step (FR-004/FR-005). Supersedes static descendant closure.
- [X] T024 [US3] Implement the soundness ledger in `src/causalshift/soundness/ledger.py`: per-run `reuse_exposure` (fraction reused, an exposure measure), and the measured false-negative RATE from ReplayDecisions + ground truth for the benchmark (FR-009, SC-002)
- [X] T025 [US3] Extend RegressionVerdict/report so any reuse surfaces `reuse_exposure` as the headline line (not mislabeled as a miss probability), per contracts/cli.md
- [X] T026 [US3] Add `--mode selective` to `causalshift evaluate` in `src/causalshift/cli.py`
- [X] T027 [P] [US3] Integration test in `tests/integration/test_us3_selective.py`: a node is reused only when its inputs are unchanged; uncertain validity ⇒ recomputed with justification; selective verdict == full verdict on the normal fixture; `reuse_exposure` present and numeric; the missing-edge case yields a measured false negative

**Checkpoint**: the distinctive contribution works and is self-reporting its own risk.

## Phase 6: Injected-fault benchmark (PRIMARY QUALITY GATE)

**Goal**: Measure SC-001..SC-005 against known ground truth. Gates merges per the constitution.

- [X] T028 Implement injected-fault generators in `benchmark/faults/inject.py`: plant a known faulty node (regressing / non-regressing), including **missing-dependency-edge** cases that create false-negative risk (spec Edge Cases; data-model.md `BenchmarkCase`)
- [X] T029 [P] Generate seeded synthetic DAG fixtures in `benchmark/fixtures/` (incl. `demo_workflow.json`, `demo_intervention.json`, `cyclic_workflow.json` used by quickstart.md), reproducible from a fixed seed
- [X] T030 Implement the benchmark runner in `benchmark/run_benchmark.py`: run selective vs full across cases, emit ComparisonReport — detection_agreement, missed_regressions (false negatives), attribution_accuracy, call_count, token_cost, latency_ms (data-model.md `ComparisonReport`; FR-010)
- [X] T031 Add gate assertions in `benchmark/run_benchmark.py`: compare measured metrics to SC targets (SC-001 ≥0.95, SC-002 ≤0.05, SC-003 call_ratio <1.0 vs the fair single-pass baseline, SC-004 ≥0.80); print measured values (measured-not-asserted) and exit non-zero if ANY criterion fails (all thresholds gate; soundness non-negotiable)
- [X] T032 Wire `causalshift benchmark [--json]` in `src/causalshift/cli.py` per contracts/cli.md
- [X] T033 [P] Test the benchmark harness in `tests/integration/test_benchmark_gate.py`: a deliberately unsound reuse rule makes false negatives rise and the gate fail (proves the gate actually bites)

**Checkpoint**: every SC claim is now measured against ground truth, reproducibly, offline.

## Phase 7: Polish & Cross-Cutting

- [X] T034 [P] Write `README.md`: what CausalShift is, the quickstart scenarios, and **honest positioning** vs CAR, CausalFlow, Tracely, DeepEval with no overstated novelty (Constitution Principle V)
- [X] T035 [P] Claims-traceability pass: every claim in README/docs points to the test or benchmark that backs it (Constitution: Quality Gates)
- [X] T036 [P] Measured-vs-assumed audit across all CLI/report output in `src/causalshift/report/` (FR-012)
- [X] T037 Verify `quickstart.md` runs end to end against the built package; fix any drift
- [X] T038 [P] Package metadata + install check (`pip install -e .`, `causalshift --help`), and a short CONTRIBUTING note on the benchmark being the merge gate

## Phase 8: v0.2 — Sound Selective Replay (review response)

Hardening from the static code review; soundness and fair measurement.

- [X] T039 Fail closed: `verdict_exit_code` + CLI returns exit 2 when any
  trajectory is inconclusive (backend could not recompute), never a silent pass
  (`report/verdict.py`, `cli.py`; contracts/cli.md). Tests in
  `tests/unit/test_exit_code.py`.
- [X] T040 Rename `false_negative_risk` → `reuse_exposure` everywhere and relabel
  it as an exposure measure, reserving "false-negative rate" for the benchmark
  (`models.py`, `report/verdict.py`, CLI, data-model/spec/contracts).
- [X] T041 Make full re-execution a single deterministic topological pass (one
  recompute per node); remove the non-terminating fixpoint loop for a FAIR
  baseline (`replay/engine.py`). Stochastic-termination test in
  `tests/integration/test_soundness_paths.py`.
- [X] T042 Dynamic selective pruning: recompute only targets + changed-input
  nodes, reuse unchanged descendants (`replay/engine.py`).
- [X] T043 Benchmark gate enforces ALL success criteria; call-ratio criterion is
  the honest "< 1.0 vs the fair baseline" with the measured ratio reported
  (`benchmark/run_benchmark.py`).
- [X] T044 Soundness-path tests: unavailable backend → inconclusive/fail-closed,
  selective target unavailable (`tests/integration/test_soundness_paths.py`).
- [X] T045 [FR-014] Light instrumentation seam `causalshift/instrument.py`
  (`@agent.node(deps=...)` auto-captures inputs/outputs/fingerprints; declare
  deps once); example `examples/instrumented_agent.py`; tests
  `tests/integration/test_instrument.py` (trace validates, round-trips, and its
  fingerprints are reusable by the validity predicate).
- [X] T046 [FR-014] Wire the seam into a live end-to-end demo
  `examples/live_agent.py --evaluate` (record on Ollama + evaluate a prompt
  change; recording and replay share prompt-construction).

## Phase 9: Adoption — legibility, backends, framework capture

- [X] T047 One-command risk report: `causalshift diff` + `report/diff.py`
  (PASS/FAIL/INCONCLUSIVE + impact/CI + changed step + calls saved + exposure);
  tests in `tests/unit/test_diff_report.py`.
- [X] T048 Benchmark reports a 95% bootstrap CI on the missed-regression rate +
  aggregate `reuse_exposure` + a dependency-completeness note
  (`benchmark/run_benchmark.py`, `ComparisonReport`).
- [X] T049 [FR-015] Framework capture adapters: generic `adapters/spans.py`
  (span→trace core) + `adapters/langgraph.py` (live-tested) + `adapters/mlflow.py`
  + `adapters/crewai.py`; examples + `tests/integration/test_adapters.py`,
  `test_langgraph_adapter.py`. OpenAI Agents SDK / LlamaIndex route via the span
  core. All carry the missing-edge caveat.
- [X] T050 Cloud recompute backends `backends/cloud.py` (OpenAI, Anthropic): key
  from env, never logged; fail closed to `Unavailable`; `--backend openai|anthropic`
  on evaluate/diff; `tests/unit/test_cloud_backend.py` (offline — no live calls).
- [X] T051 Project hygiene: MIT LICENSE, GitHub Actions CI (pytest + offline
  benchmark gate), repo description/topics.

## Phase 10: Statistical rigor (review response)

- [X] T052 [FR-016] Fail closed on insufficient evidence: three-way verdict
  status (PASS/FAIL/INCONCLUSIVE), minimum usable-sample requirement, optional
  non-inferiority margin; `report/verdict.py`, `models.py`;
  `tests/unit/test_evidence.py` (empty/tiny samples no longer pass).
- [X] T053 [FR-017] Benchmark measures the false-negative rate vs INDEPENDENT
  ground truth (not full_replay) and reports `full_missed` as an oracle-quality
  check (`benchmark/run_benchmark.py`, `ComparisonReport`).
- [X] T054 [FR-017] Topology × hidden-edge-frequency sweep
  (`benchmark/sweep.py`): 3 topologies (chain/deepchain/fan) × frequencies,
  false-negative rate + 95% CI + `full_missed` per condition; multi-topology via
  a `Topology` registry in `faults/inject.py` (evaluator targets each case's
  terminal). Tests in `tests/integration/test_sweep.py`.

## Dependencies & Story Completion Order

- **Setup (P1 phase 1)** → **Foundational (phase 2)** block everything.
- **US1 (P1)** depends only on Foundational → it is the MVP and ships first.
- **US2 (P2)** depends on US1 (needs the verdict/effect machinery).
- **US3 (P3)** depends on Foundational + US1 (compares against full re-execution); it introduces reuse and the false-negative metric.
- **Benchmark (phase 6)** depends on US1 + US3 (needs both modes to compare) and on US2 for attribution_accuracy.
- **Polish (phase 7)** last.

## Parallel Execution Examples

- Phase 1: T002, T003 in parallel after T001.
- Phase 2: T007 ∥ T009 ∥ T011 (tests/backends in different files) once their targets (T006/T008/T010) exist.
- Across stories, tests marked [P] (T018, T021, T027, T033) touch separate files and can run in parallel within their phase.

## Implementation Strategy

- **MVP = Phase 1 + Phase 2 + Phase 3 (US1).** That alone delivers a sound,
  usable verdict via full re-execution — valuable and shippable before any
  selective-replay work exists.
- Then US2 (attribution), then US3 (the distinctive selective replay). The
  benchmark (Phase 6) is built as soon as US3 lands and becomes the gate for all
  further changes. Soundness and the measured false-negative rate are never
  deferred past the feature that introduces reuse.
