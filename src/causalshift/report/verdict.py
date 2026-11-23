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
    fn_risk = None
    if mode == "selective":
        fn_risk = reuse_fraction(results)
        notes.append(
            "false_negative_risk is an UPPER BOUND (reuse fraction) at eval time; "
            "the true rate is MEASURED only by `causalshift benchmark`"
        )
    if inconclusive:
        notes.append(f"{inconclusive} trajectory(ies) inconclusive (backend could not "
                     f"recompute an affected node) — excluded, never counted as safe")

    return RegressionVerdict(
        workflow_id=workflow_id, mode=mode, n_trajectories=len(results),
        regressed=regressed, magnitude=mean, ci_low=lo, ci_high=hi,
        attribution=attribution or [], false_negative_risk=fn_risk,
        inconclusive=inconclusive, notes=notes,
    )


def format_verdict(v: RegressionVerdict) -> str:
    lines = [
        f"CausalShift verdict [{v.workflow_id}] mode={v.mode}",
        f"  trajectories      {v.n_trajectories} (inconclusive: {v.inconclusive})",
        f"  regressed         {'YES' if v.regressed else 'no'}",
        f"  magnitude         {v.magnitude:+.4f}  (95% CI [{v.ci_low:+.4f}, {v.ci_high:+.4f}])",
    ]
    if v.false_negative_risk is not None:
        lines.append(f"  false_negative_risk (HEADLINE)  {v.false_negative_risk:.3f}  "
                     f"[upper bound = reuse fraction]")
    if v.attribution:
        top = ", ".join(f"{n} ({c:+.3f})" for n, c in v.attribution[:3])
        lines.append(f"  attribution       {top}")
    for n in v.notes:
        lines.append(f"  · {n}")
    return "\n".join(lines)
