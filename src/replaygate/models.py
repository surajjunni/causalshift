"""Core entities (data-model.md). Deliberately storage-agnostic dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

REUSED = "reused"
RECOMPUTED = "recomputed"


@dataclass
class Cost:
    tokens: int = 0
    latency_ms: float = 0.0


@dataclass
class Step:
    step_index: int
    node_name: str
    input_fingerprint: str      # mandatory (data-model.md Step.input_fingerprint)
    output: str
    model_id: str
    prompt_id: str
    cost: Cost = field(default_factory=Cost)


@dataclass
class GroundTruth:
    fault_node: Optional[str]   # which node carries the planted fault, if any
    regresses: bool             # whether this change truly regresses quality


@dataclass
class Trajectory:
    trajectory_id: str
    workflow_id: str
    steps: list[Step]
    ground_truth: Optional[GroundTruth] = None

    def output_map(self) -> dict[str, str]:
        return {s.node_name: s.output for s in self.steps}

    def models(self) -> dict[str, tuple[str, str]]:
        return {s.node_name: (s.model_id, s.prompt_id) for s in self.steps}


@dataclass
class Workflow:
    workflow_id: str
    nodes: list[str]
    edges: list[tuple[str, str]]          # declared dependency edges (src -> dst)
    trajectories: list[Trajectory] = field(default_factory=list)
    prompts: dict[str, str] = field(default_factory=dict)  # prompt_id -> system prompt text
    # "declared" = dependencies were explicitly instrumented; "unverified" = captured from
    # control-flow only (e.g. a LangGraph graph) so declared edges may be incomplete.
    dependency_coverage: str = "declared"


@dataclass
class Intervention:
    """Substitute model/prompt at named nodes. targets[node] = {'model_id'|'prompt_id': ...}."""
    workflow_id: str
    targets: dict[str, dict[str, str]]

    def effective(self, node: str, model_id: str, prompt_id: str) -> tuple[str, str]:
        t = self.targets.get(node, {})
        return t.get("model_id", model_id), t.get("prompt_id", prompt_id)


@dataclass
class ReplayDecision:
    step_index: int
    node_name: str
    action: str                 # REUSED | RECOMPUTED
    justification: str
    in_affected_set: bool
    validity_valid: Optional[bool] = None   # predicate outcome (None if not checked)


@dataclass
class ReplayResult:
    trajectory_id: str
    mode: str                   # "full" | "selective"
    decisions: list[ReplayDecision]
    candidate_outputs: dict[str, str]
    quality_score: float
    baseline_score: float
    calls: int
    tokens: int
    latency_ms: float
    inconclusive: bool = False

    @property
    def delta(self) -> float:
        """candidate - baseline; higher quality is better, so negative = worse."""
        return self.quality_score - self.baseline_score


@dataclass
class RegressionVerdict:
    workflow_id: str
    mode: str
    n_trajectories: int
    regressed: bool
    magnitude: float            # mean delta (negative = quality dropped)
    ci_low: float
    ci_high: float
    attribution: list[tuple[str, float]] = field(default_factory=list)  # (node, contribution)
    reuse_exposure: Optional[float] = None   # fraction of nodes reused (NOT a probability)
    inconclusive: int = 0
    status: Optional[str] = None             # "PASS" | "FAIL" | "INCONCLUSIVE"
    n_usable: int = 0                        # trajectories with a usable (conclusive) delta
    notes: list[str] = field(default_factory=list)  # measured-vs-assumed tags


@dataclass
class BenchmarkCase:
    case_id: str
    workflow: Workflow
    intervention: Intervention
    fault_node: Optional[str]
    regresses: bool             # ground-truth label
    missing_edge: bool = False  # declared graph omits a true dependency


@dataclass
class ComparisonReport:
    n_cases: int
    detection_agreement: float
    missed_regressions: float   # false-negative rate (selective says safe, full says regressed)
    attribution_accuracy: float
    selective_calls: int
    full_calls: int
    selective_tokens: int
    full_tokens: int
    selective_latency_ms: float
    full_latency_ms: float
    missed_ci_low: float = 0.0       # 95% bootstrap CI on the missed-regression rate
    missed_ci_high: float = 0.0
    reuse_exposure: float = 0.0      # aggregate fraction of nodes reused by selective
    full_missed: float = 0.0         # full re-execution's own miss rate vs independent truth

    @property
    def call_ratio(self) -> float:
        return self.selective_calls / self.full_calls if self.full_calls else 0.0
