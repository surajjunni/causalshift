"""Assemble a RegressionVerdict from per-trajectory ReplayResults, tagging
measured-vs-assumed (FR-012)."""

from __future__ import annotations

from typing import Optional

from causalshift.evaluate.population import bootstrap_mean_ci, is_regression
from causalshift.models import RegressionVerdict, ReplayResult
from causalshift.soundness.ledger import reuse_fraction


def build_verdict(workflow_id: str, mode: str, results: list[ReplayResult],
                  attribution: Optional[list[tuple[str, float]]] = None) -> RegressionVerdict:
    usable = [r for r in results if not r.inconclusive]
    inconclusive = len(results) - len(usable)
    deltas = [r.delta for r in usable]
    mean, lo, hi = bootstrap_mean_ci(deltas)
    regressed = is_regression(hi)

    notes = [
        "magnitude/CI are MEASURED by bootstrap over trajectories",
        "regressed = CI of (candidate-baseline) lies entirely below 0",
    ]
    exposure = None
    if mode == "selective":
        exposure = reuse_fraction(results)
        notes.append(
            "reuse_exposure is the fraction of nodes REUSED — an exposure measure, "
            "NOT a probability of a missed regression. The actual false-negative "
            "RATE is measured against ground truth only by `causalshift benchmark`"
        )
    if inconclusive:
        notes.append(f"{inconclusive} trajectory(ies) inconclusive (backend could not "
                     f"recompute a node) — excluded; evaluation fails closed, never 'safe'")

    return RegressionVerdict(
        workflow_id=workflow_id, mode=mode, n_trajectories=len(results),
        regressed=regressed, magnitude=mean, ci_low=lo, ci_high=hi,
        attribution=attribution or [], reuse_exposure=exposure,
        inconclusive=inconclusive, notes=notes,
    )


def verdict_exit_code(v: RegressionVerdict) -> int:
    """CI exit semantics (fail closed): 2 if any trajectory was inconclusive,
    else 1 if a regression was detected, else 0. An inconclusive run is NEVER a
    pass (Constitution: Soundness Over Savings)."""
    if v.inconclusive > 0:
        return 2
    return 1 if v.regressed else 0


def format_verdict(v: RegressionVerdict) -> str:
    lines = [
        f"CausalShift verdict [{v.workflow_id}] mode={v.mode}",
        f"  trajectories      {v.n_trajectories} (inconclusive: {v.inconclusive})",
        f"  regressed         {'YES' if v.regressed else 'no'}",
        f"  magnitude         {v.magnitude:+.4f}  (95% CI [{v.ci_low:+.4f}, {v.ci_high:+.4f}])",
    ]
    if v.reuse_exposure is not None:
        lines.append(f"  reuse_exposure    {v.reuse_exposure:.3f}  "
                     f"[fraction of nodes reused; NOT a miss probability — see benchmark]")
    if v.inconclusive:
        lines.append(f"  INCONCLUSIVE      {v.inconclusive} trajectory(ies) → fails closed (exit 2)")
    if v.attribution:
        top = ", ".join(f"{n} ({c:+.3f})" for n, c in v.attribution[:3])
        lines.append(f"  attribution       {top}")
    for n in v.notes:
        lines.append(f"  · {n}")
    return "\n".join(lines)
