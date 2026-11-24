# Phase 1 Data Model: Causal Regression Core

Entities derived from the spec's Key Entities and Functional Requirements.
Attributes are described by role, not storage type; the SQLite schema realizes
them in `src/causalshift/store/`.

## Trajectory

One recorded agent run.

- `trajectory_id` — stable identifier
- `workflow_id` — which agent/DAG it belongs to
- `steps` — ordered list of Steps
- `ground_truth` — optional (benchmark only): planted fault node + expected
  regression label

Rules: must reference a DAG workflow (FR-011); a trajectory whose declared graph
is cyclic is rejected at ingest.

## Step (Node instance)

One decision within a trajectory.

- `trajectory_id`, `step_index`, `node_name`
- `input_fingerprint` — enough of the inputs to detect whether inputs changed
  (not necessarily the raw input)
- `output` — the recorded output text
- `model_id`, `prompt_id` — what produced it (so an intervention can target it)
- `cost` — recorded tokens / latency for accounting

Rules: `input_fingerprint` is mandatory (FR-001) — a step lacking it cannot be
soundly reused and is always recomputed when in scope.

## Dependency Edge

A declared data-flow dependency between steps.

- `workflow_id`, `src_node`, `dst_node`
- meaning: `dst_node`'s input depends on `src_node`'s output

Rules: edges define the causal-closure used to compute the affected set.
Completeness of edges is the soundness basis; a missing edge is the primary
false-negative source the benchmark probes.

## Intervention

The proposed change under test.

- `targets` — list of (`node_name`, new `model_id` and/or new `prompt_id`)
- `scope` — which workflow it applies to

## ReplayDecision (per step, per trajectory, per run)

- `step_index`, `node_name`
- `action` — `reused` | `recomputed`
- `justification` — why reuse was sound, or why it was recomputed
- `in_affected_set` — bool; v0.2 meaning: this node was FORCED to recompute
  because it is an intervention target (selective replay no longer precomputes a
  static descendant closure — see Rules)
- `validity_checked` — bool, and predicate outcome

Rules (soundness ledger, v0.2 dynamic pruning): a node is recomputed iff it is
an intervention target OR its declared inputs actually changed (the validity
predicate fails); otherwise it is `reused` (pruned). `action = reused` therefore
requires `validity_checked = valid`. Any uncertain validity ⇒ `recomputed`
(fail toward recompute).

## ReplayResult (per trajectory)

- `trajectory_id`, `mode` (`full` | `selective`)
- `decisions` — list of ReplayDecision
- `candidate_outputs` — outputs after the intervention
- `quality_score` — from the configured evaluator (baseline vs candidate)
- `calls`, `tokens`, `latency_ms` — cost actually incurred

## RegressionVerdict (population-level)

- `intervention`, `n_trajectories`
- `status` — `PASS` | `FAIL` | `INCONCLUSIVE` (fail closed on insufficient
  evidence); `regressed` is the legacy bool (= status FAIL)
- `n_usable` — usable (conclusive) trajectories; below the minimum ⇒ INCONCLUSIVE
- `magnitude`, `ci_low`, `ci_high`
- `attribution` — ranked responsible node(s) with confidence
- `reuse_exposure` — fraction of nodes reused (headline for any reuse); an
  exposure measure, NOT a false-negative probability. The empirical
  false-negative rate is measured by the benchmark, not per-run.
- `inconclusive` — count of trajectories the backend could not recompute; a run
  with any inconclusive trajectory fails closed (CLI exit 2), never "safe"
- `measured_vs_assumed` — tags on each reported figure

## BenchmarkCase

- `case_id`, `trajectories`, planted `fault_node`, expected `regresses` label,
  and whether it includes a `missing_edge` (to probe false negatives)

## ComparisonReport (selective vs full)

- per metric: `detection_agreement`, `missed_regressions` (false-negative rate)
  with `missed_ci_low` / `missed_ci_high` (Wilson 95% CI over labeled cases),
  `attribution_accuracy`, `reuse_exposure` (aggregate fraction of nodes reused),
  `call_count`, `token_cost`, `latency_ms`, plus `full_missed` (full
  re-execution's own miss rate vs truth — an oracle-quality check)
- the headline false-negative rate is measured vs INDEPENDENT ground truth and
  carries its CI; other metrics report uncertainty where applicable
