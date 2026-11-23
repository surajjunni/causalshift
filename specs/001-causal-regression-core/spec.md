# Feature Specification: Causal Regression Core

**Feature Branch**: `001-causal-regression-core`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "CausalShift core — causal regression testing for a model/prompt change against recorded LLM-agent trajectories."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trustworthy go/no-go verdict for a change (Priority: P1)

An engineer is about to swap the model (or edit a prompt) behind a production
LLM agent. Before shipping, they point CausalShift at a set of recorded real
trajectories and the proposed change. They get back a population-level verdict:
*did quality regress, by how much, and how confident is that answer* — not from
hand-written test cases, but from their own recorded traffic.

**Why this priority**: This is the core value. Without a trustworthy verdict
there is no product. It is achievable on its own using sound full re-execution
as the baseline (no state reuse), delivering value even before any efficiency
work exists.

**Independent Test**: Run on an injected-fault benchmark where ground truth is
known; confirm the verdict (regressed / not) and the magnitude's confidence
interval match the planted effect across many trajectories.

**Acceptance Scenarios**:

1. **Given** a set of recorded trajectories and an intervention that planted a
   real quality regression, **When** the user runs an evaluation, **Then** the
   report states that quality regressed, gives the magnitude with a confidence
   interval, and separates the real effect from sampling noise.
2. **Given** trajectories and an intervention that changes nothing meaningful,
   **When** the user runs an evaluation, **Then** the report does not raise a
   regression beyond the stated false-alarm rate.

---

### User Story 2 - Localize the responsible decision (Priority: P2)

When a regression is found, the engineer needs to know *which* step caused it —
was it the reasoning step, the tool selection, the retrieval? CausalShift
attributes the regression to the responsible node(s) so they can act.

**Why this priority**: "Something got worse" is far less useful than "the
planner step got worse." Attribution is what turns a verdict into a fix. It
builds on P1 but is independently testable.

**Independent Test**: On injected-fault benchmarks where the faulty node is
known, confirm the attribution names the correct node at or above the target
accuracy.

**Acceptance Scenarios**:

1. **Given** a regression caused by a known node, **When** the user views the
   report, **Then** the responsible node is named with a confidence measure.
2. **Given** a regression with interacting contributors, **When** the user views
   the report, **Then** contribution is split across nodes rather than assigned
   wholly to one.

---

### User Story 3 - Same verdict, far cheaper, with measured soundness (Priority: P3)

The engineer wants the verdict without paying to re-run every step of every
trajectory. CausalShift recomputes only the causally-affected nodes and reuses
recorded outputs elsewhere — but only where that reuse is provably sound — and
reports the measured risk that reuse caused a missed regression.

**Why this priority**: This is the distinctive efficiency contribution, but it
must not come before a trustworthy verdict exists. Reuse introduces the
possibility of silently missing a regression, so it ships only once that risk
can be measured and bounded.

**Independent Test**: On the injected-fault benchmark, compare selective replay
against full re-execution: detection agreement, missed regressions (false
negatives), attribution accuracy, model-call count, token cost, and latency.

**Acceptance Scenarios**:

1. **Given** an intervention, **When** the user runs selective replay, **Then**
   it reaches the same regression verdict as full re-execution on the benchmark
   at or above the detection-agreement target, using materially fewer model
   calls.
2. **Given** a step whose input validity under the change is uncertain, **When**
   selective replay processes it, **Then** it recomputes that step rather than
   reusing the recorded output, and records why.
3. **Given** any run that reused recorded state, **When** the user views the
   report, **Then** the measured false-negative risk (or its bound) is shown as
   the headline figure.

---

### Edge Cases

- **Missing dependency edge**: a step's real input changed under the
  intervention but the declared dependency graph omits that edge. This is the
  core soundness threat; the benchmark MUST include such cases and the
  false-negative rate MUST capture them.
- **Uncertain validity**: when it cannot be proven that a reused step's inputs
  and environment still hold, the system recomputes (fails toward recompute).
- **Intervention with no downstream dependents**: only the intervened node is
  recomputed; the rest is reused soundly.
- **Out-of-contract agent**: cyclic or opaque-stateful trajectories are rejected
  or clearly flagged, not silently analyzed.
- **True negative**: a change that does not regress must not trigger a verdict
  beyond the stated false-alarm rate.
- **Sampling noise**: apparent differences within noise must be reported as "no
  significant regression," not a regression.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST ingest recorded agent trajectories that retain, per
  step: node identity, enough of the step's inputs to detect whether inputs
  changed, the step's output, and the declared dependency edges between steps.
- **FR-002**: System MUST accept an intervention specification that substitutes
  a different model or prompt at one or more named nodes.
- **FR-003**: System MUST provide a sound full re-execution baseline that
  recomputes the affected trajectory without reusing recorded state.
- **FR-004**: System MUST provide selective replay that recomputes only
  causally-affected nodes and reuses a recorded output ONLY when that step's
  relevant inputs and environmental assumptions are provably still valid.
- **FR-005**: When reuse validity is uncertain, the system MUST escalate to
  recomputation rather than reuse, and MUST record the reason for every
  reuse-vs-recompute decision.
- **FR-006**: System MUST evaluate a change across many trajectories
  (population-level), not a single run.
- **FR-007**: System MUST report whether quality regressed, the magnitude, and a
  confidence interval, separating real effect from sampling variation.
- **FR-008**: System MUST attribute a detected regression to the responsible
  node(s), with a confidence measure.
- **FR-009**: System MUST always measure and report, as the headline figure, the
  false-negative risk (or an upper bound) introduced by any state reuse.
- **FR-010**: System MUST produce a comparison of selective replay versus full
  re-execution covering: detection agreement, missed regressions, attribution
  accuracy, model-call count, token cost, and wall-clock latency.
- **FR-011**: System MUST reject or clearly flag trajectories outside the
  supported contract (cyclic or opaque-stateful agents).
- **FR-012**: System MUST distinguish measured results from modeling assumptions
  in all user-facing output.
- **FR-013**: System MUST provide an injected-fault benchmark with known ground
  truth so that attribution accuracy and false-negative rate are measurable, and
  the benchmark MUST be runnable reproducibly without any paid-API dependency.

### Key Entities *(include if feature involves data)*

- **Trajectory**: one recorded agent run as an ordered set of steps plus its
  declared dependency structure.
- **Step / Node**: a single decision in a trajectory — identity, inputs (for
  change detection), output, and incoming/outgoing dependency edges.
- **Dependency edge**: a declared "this step's input depends on that step's
  output" relationship; completeness of these edges is the soundness basis.
- **Intervention**: the proposed change — which model/prompt replaces which at
  which node(s).
- **Replay result**: per-trajectory outcome of an intervention, recording for
  each step whether it was reused or recomputed and why.
- **Regression verdict**: population-level outcome — regressed or not, magnitude,
  confidence interval, responsible node(s), and the reuse false-negative risk.
- **Benchmark case**: a trajectory set with a planted fault and known ground
  truth (which node, whether it regresses) used to measure accuracy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the injected-fault benchmark, selective replay reaches the same
  regression verdict as the full re-execution baseline on at least 95% of cases
  (detection agreement).
- **SC-002**: The missed-regression (false-negative) rate of selective replay is
  measured on the benchmark and is at most 5%, and is always reported with the
  verdict.
- **SC-003**: Selective replay reaches the verdict using at most 50% of the
  model calls required by full re-execution, at equal detection agreement.
- **SC-004**: Regression attribution names the responsible node with at least
  80% accuracy on single-fault benchmark cases.
- **SC-005**: Every reported regression magnitude carries a confidence interval,
  and on no-regression (true-negative) cases the false-alarm rate is at most 5%.
- **SC-006**: A user obtains a change verdict across a set of recorded
  trajectories without writing any per-case test by hand.

## Assumptions

- The numeric targets in SC-001 through SC-005 (95% agreement, ≤5% false
  negatives, ≤50% calls, ≥80% attribution, ≤5% false alarms) are v1 targets to
  be calibrated against the benchmark; they are reported as measured values and
  revised only with evidence, never asserted.
- Trajectories are supplied by an upstream, explicitly instrumented capture step
  that retains inputs and dependency edges; producing that instrumentation for
  arbitrary agents is out of scope for this feature.
- v1 covers deterministic, DAG-style agents only; cyclic and opaque-stateful
  agents are out of scope and handled by rejection/flagging (FR-011).
- A locally runnable model is available for recomputation during benchmarking,
  so the core benchmark needs no paid API.
- "Quality" is judged by a configurable evaluator applied consistently to
  baseline and candidate outputs; defining the evaluator itself is upstream of
  this feature.
