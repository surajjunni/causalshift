"""Assemble a RegressionVerdict from per-trajectory ReplayResults, tagging
measured-vs-assumed (FR-012)."""

from __future__ import annotations

from typing import Optional

from replaygate.evaluate.population import bootstrap_mean_ci, is_regression
from replaygate.models import RegressionVerdict, ReplayResult
from replaygate.soundness.ledger import reuse_fraction


def build_verdict(workflow_id: str, mode: str, results: list[ReplayResult],
                  attribution: Optional[list[tuple[str, float]]] = None,
                  min_samples: int = 3, epsilon: float = 0.0) -> RegressionVerdict:
    """Three-way, fail-closed verdict.

    - INCONCLUSIVE (exit 2) if any trajectory was inconclusive OR there are fewer
      than `min_samples` usable trajectories (insufficient evidence — never a
      silent PASS), OR (when a non-inferiority margin `epsilon` > 0 is set) the CI
      straddles the margin so non-regression cannot be demonstrated.
    - FAIL (exit 1) if the CI of (candidate - baseline) lies below -epsilon.
    - PASS (exit 0) only with enough evidence that quality did not regress.
    """
    usable = [r for r in results if not r.inconclusive]
    inconclusive = len(results) - len(usable)
    deltas = [r.delta for r in usable]
    mean, lo, hi = bootstrap_mean_ci(deltas)
    regressed = hi < -epsilon

    enough = len(usable) >= min_samples and inconclusive == 0
    if not enough:
        status = "INCONCLUSIVE"
    elif regressed:
        status = "FAIL"
    elif lo < -epsilon:
        # The CI crosses the degradation boundary -epsilon, so non-regression is NOT
        # demonstrated. Applies at the zero-margin default too: a CI straddling 0 is
        # INCONCLUSIVE, never a silent PASS (fail closed; keeps PASS consistent with
        # "the whole 95% CI is above the boundary").
        status = "INCONCLUSIVE"
    else:
        status = "PASS"

    notes = [
        "magnitude/CI are MEASURED by bootstrap over trajectories",
        f"status fail-closed: need >= {min_samples} usable trajectories and no "
        f"inconclusive ones to conclude (usable={len(usable)}, inconclusive={inconclusive})",
        f"regressed = CI upper bound lies below -epsilon; PASS requires the whole CI "
        f"at or above -epsilon (epsilon={epsilon})",
    ]
    exposure = None
    if mode == "selective":
        exposure = reuse_fraction(results)
        notes.append(
            "reuse_exposure is the fraction of nodes REUSED — an exposure measure, "
            "NOT a probability of a missed regression. The actual false-negative "
            "RATE is measured against ground truth only by `replaygate benchmark`"
        )
    if inconclusive:
        notes.append(f"{inconclusive} trajectory(ies) inconclusive (backend could not "
                     f"recompute a node) — excluded; evaluation fails closed, never 'safe'")

    return RegressionVerdict(
        workflow_id=workflow_id, mode=mode, n_trajectories=len(results),
        regressed=(status == "FAIL"), magnitude=mean, ci_low=lo, ci_high=hi,
        attribution=attribution or [], reuse_exposure=exposure,
        inconclusive=inconclusive, notes=notes, status=status, n_usable=len(usable),
    )


def verdict_exit_code(v: RegressionVerdict) -> int:
    """CI exit semantics (fail closed): 0 PASS / 1 FAIL / 2 INCONCLUSIVE. An
    inconclusive or insufficient-evidence run is NEVER a pass (Constitution:
    Soundness Over Savings)."""
    if v.status is not None:
        return {"PASS": 0, "FAIL": 1, "INCONCLUSIVE": 2}.get(v.status, 2)
    # fallback for directly-constructed verdicts without a status
    if v.inconclusive > 0:
        return 2
    return 1 if v.regressed else 0


def format_verdict(v: RegressionVerdict) -> str:
    lines = [
        f"ReplayGate verdict [{v.workflow_id}] mode={v.mode}",
        f"  status            {v.status or ('FAIL' if v.regressed else 'PASS')}",
        f"  trajectories      {v.n_trajectories} (usable: {v.n_usable}, "
        f"inconclusive: {v.inconclusive})",
        f"  magnitude         {v.magnitude:+.4f}  (95% CI [{v.ci_low:+.4f}, {v.ci_high:+.4f}])",
    ]
    if v.status == "INCONCLUSIVE" and v.inconclusive == 0:
        lines.append("  reason            insufficient evidence (too few usable "
                     "trajectories) → fails closed")
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
