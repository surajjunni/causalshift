"""Plain-language 'change risk report' for `causalshift diff` — the job-to-be-done
front door: is this model/prompt change safe to ship, by how much, which step,
and how many model calls it saved. Pure formatter so it is testable offline."""

from __future__ import annotations

from causalshift.models import RegressionVerdict
from causalshift.report.verdict import verdict_exit_code

_STATUS = {
    0: "PASS — no regression detected",
    1: "FAIL — quality regresses",
    2: "INCONCLUSIVE — insufficient evidence (fails closed, blocks deploy)",
}


def diff_report(verdict: RegressionVerdict, targets: list[str],
                selective_calls: int, full_estimate: int) -> str:
    code = verdict_exit_code(verdict)
    saved = max(0, full_estimate - selective_calls)
    pct = (saved / full_estimate * 100) if full_estimate else 0.0

    lines = [
        f"CausalShift — change risk report [{verdict.workflow_id}]",
        f"  change:       {', '.join(targets) or '(none)'}",
        f"  verdict:      {_STATUS[code]}",
        f"  impact:       {verdict.magnitude:+.3f} mean quality "
        f"(95% CI [{verdict.ci_low:+.3f}, {verdict.ci_high:+.3f}])",
        f"  changed step: {', '.join(targets) or '(none)'}"
        + (f"   (attribution: {verdict.attribution[0][0]})" if verdict.attribution else ""),
        f"  cost:         selective made {selective_calls} model call(s); "
        f"full re-execution ≈ {full_estimate} (saved ~{saved}, {pct:.0f}%)",
    ]
    if verdict.reuse_exposure is not None:
        lines.append(f"  reuse:        exposure {verdict.reuse_exposure:.2f} "
                     f"(fraction of nodes reused) — an exposure measure, not a miss probability")
    if verdict.inconclusive:
        lines.append(f"  note:         {verdict.inconclusive} trajectory(ies) inconclusive "
                     f"(backend could not recompute) → treated as unsafe")
    lines.append("  soundness:    run `causalshift benchmark` for the measured "
                 "false-negative rate + 95% CI on labeled cases")
    lines.append(f"  exit:         {code}  (0 PASS / 1 FAIL / 2 INCONCLUSIVE)")
    return "\n".join(lines)
