"""Plain-language 'change risk report' for `replaygate diff` — the job-to-be-done
front door: is this model/prompt change safe to ship, by how much, which step,
and how many model calls it saved. Pure formatter so it is testable offline.

Renders text (default) or markdown (`fmt="markdown"`, for pasting into a PR/CI
comment). The verdict/exit semantics live in report.verdict; this only presents."""

from __future__ import annotations

from replaygate.models import RegressionVerdict
from replaygate.report.verdict import verdict_exit_code

_GLYPH = {0: "✓", 1: "✗", 2: "?"}
_WORD = {
    0: "PASS — no regression detected",
    1: "FAIL — quality regresses",
    2: "INCONCLUSIVE — insufficient evidence (fails closed, blocks deploy)",
}


def _inconclusive_reason(v: RegressionVerdict, margin: float, min_samples: int) -> str:
    """Which fail-closed path produced the INCONCLUSIVE (best-effort from the verdict)."""
    if v.inconclusive > 0:
        return (f"{v.inconclusive} trajectory(ies) could not be recomputed "
                "(backend unavailable); enable a recompute backend and re-run")
    if v.n_usable < min_samples:
        return (f"too few usable trajectories ({v.n_usable} < {min_samples}) for a "
                "confident call; record and ingest more trajectories")
    if margin > 0 and v.ci_low < -margin <= v.ci_high:
        return ("the 95% CI straddles the non-inferiority margin, so non-regression "
                "cannot be demonstrated")
    return "insufficient statistical evidence to conclude"


def _recommendation(v: RegressionVerdict, code: int, margin: float, min_samples: int) -> str:
    if code == 0:
        return "Safe to ship: quality did not drop beyond the margin (95% CI stays above it)."
    if code == 1:
        return "Don't ship: quality regresses — the 95% CI is entirely past the margin."
    return "Can't decide (blocks deploy): " + _inconclusive_reason(v, margin, min_samples)


def _impact_gloss(v: RegressionVerdict) -> str:
    if abs(v.magnitude) < 1e-9:
        return "no measurable change in mean quality"
    direction = "lower" if v.magnitude < 0 else "higher"
    return f"candidate scores {abs(v.magnitude):.3f} {direction} on average"


def _attribution_node(v: RegressionVerdict, targets: list[str]):
    """Return the top responsible node only when it adds info beyond the change target."""
    if not v.attribution:
        return None
    node, contrib = v.attribution[0]
    if len(targets) == 1 and node == targets[0]:
        return None
    return node, contrib


def diff_report(verdict: RegressionVerdict, targets: list[str],
                selective_calls: int, full_estimate: int,
                margin: float = 0.0, min_samples: int = 3, fmt: str = "text") -> str:
    code = verdict_exit_code(verdict)
    saved = max(0, full_estimate - selective_calls)
    pct = (saved / full_estimate * 100) if full_estimate else 0.0
    change = ", ".join(targets) or "(none)"
    attr = _attribution_node(verdict, targets)
    impact = (f"{verdict.magnitude:+.3f} mean quality (95% CI "
              f"[{verdict.ci_low:+.3f}, {verdict.ci_high:+.3f}], margin {-margin:+.3f}) "
              f"— {_impact_gloss(verdict)}")
    cost = (f"selective made {selective_calls} model call(s); "
            f"full re-execution ≈ {full_estimate} (saved ~{saved}, {pct:.0f}%)")
    reuse = (f"{verdict.reuse_exposure:.2f} — fraction of nodes reused, not a miss "
             "probability") if verdict.reuse_exposure is not None else None
    soundness = ("run `replaygate benchmark` for the measured false-negative rate "
                 "(95% CI) on labeled cases")
    rec = _recommendation(verdict, code, margin, min_samples)

    if fmt == "markdown":
        rows = [("change", f"`{change}`"), ("impact", impact)]
        if attr:
            rows.append(("attribution", f"`{attr[0]}` ({attr[1]:+.3f})"))
        rows.append(("cost", cost))
        if reuse:
            rows.append(("reuse exposure", reuse))
        rows.append(("soundness", soundness))
        rows.append(("exit", f"{code}  (0 PASS / 1 FAIL / 2 INCONCLUSIVE)"))
        body = "\n".join(f"| {k} | {v} |" for k, v in rows)
        return (f"### ReplayGate — change risk report `{verdict.workflow_id}`\n\n"
                f"**{_GLYPH[code]} {_WORD[code]}**\n\n{rec}\n\n"
                f"| field | value |\n|---|---|\n{body}\n")

    lines = [
        f"ReplayGate — change risk report [{verdict.workflow_id}]",
        "",
        f"  {_GLYPH[code]} {_WORD[code]}",
        f"  → {rec}",
        "",
        f"  change:       {change}",
        f"  impact:       {impact}",
    ]
    if attr:
        lines.append(f"  attribution:  {attr[0]} ({attr[1]:+.3f})  "
                     "(step most responsible for the change)")
    lines.append(f"  cost:         {cost}")
    if reuse:
        lines.append(f"  reuse:        exposure {reuse}")
    lines.append(f"  soundness:    {soundness}")
    lines.append(f"  exit:         {code}  (0 PASS / 1 FAIL / 2 INCONCLUSIVE)")
    return "\n".join(lines)
