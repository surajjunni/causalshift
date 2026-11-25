"""The diff risk-report formatter (offline, pure)."""

from replaygate.models import RegressionVerdict
from replaygate.report.diff import diff_report


def _v(regressed, inconclusive=0, exposure=0.75):
    return RegressionVerdict(workflow_id="w", mode="selective", n_trajectories=4,
                             regressed=regressed, magnitude=-0.72, ci_low=-0.9, ci_high=-0.4,
                             reuse_exposure=exposure, inconclusive=inconclusive)


def test_fail_report_shows_verdict_cost_and_exposure():
    r = diff_report(_v(True), targets=["responder"], selective_calls=4, full_estimate=12)
    assert "FAIL — quality regresses" in r
    assert "responder" in r
    assert "saved ~8, 67%" in r
    assert "exposure 0.75" in r
    assert "exit:         1" in r


def test_pass_report():
    r = diff_report(_v(False, exposure=0.5), targets=["planner"], selective_calls=2, full_estimate=12)
    assert "PASS — no material regression" in r
    assert "exit:         0" in r


def test_inconclusive_report_blocks():
    r = diff_report(_v(False, inconclusive=2), targets=["x"], selective_calls=0, full_estimate=8)
    assert "INCONCLUSIVE" in r and "blocks deploy" in r
    assert "exit:         2" in r


# --- new UX ---

def test_fail_banner_and_recommendation():
    r = diff_report(_v(True), targets=["responder"], selective_calls=4, full_estimate=12)
    assert "✗ FAIL" in r
    assert "Don't ship" in r
    assert "lower on average" in r          # plain-language impact gloss


def test_pass_banner_and_recommendation():
    r = diff_report(_v(False, exposure=0.5), targets=["planner"], selective_calls=2, full_estimate=12)
    assert "✓ PASS" in r
    assert "No material regression" in r
    assert "Not a broader safety guarantee" in r


def test_margin_is_shown():
    r = diff_report(_v(True), targets=["responder"], selective_calls=4, full_estimate=12, margin=0.1)
    assert "margin -0.100" in r


def test_markdown_format():
    r = diff_report(_v(True), targets=["responder"], selective_calls=4, full_estimate=12,
                    fmt="markdown")
    assert r.startswith("### ReplayGate")
    assert "| field | value |" in r
    assert "**✗ FAIL" in r


def test_zero_margin_inconclusive_names_boundary_reason():
    # at the zero-margin default, a CI straddling 0 is INCONCLUSIVE and the report must give
    # the specific CI-crossing reason, not a generic one (review P3).
    v = RegressionVerdict(workflow_id="w", mode="selective", n_trajectories=4, regressed=False,
                          magnitude=-0.05, ci_low=-0.2, ci_high=0.1, inconclusive=0,
                          status="INCONCLUSIVE", n_usable=4)
    r = diff_report(v, targets=["x"], selective_calls=0, full_estimate=4)  # margin=0 default
    assert "crosses the degradation boundary" in r


def test_inconclusive_insufficient_evidence_reason():
    v = RegressionVerdict(workflow_id="w", mode="selective", n_trajectories=2, regressed=False,
                          magnitude=-0.1, ci_low=-0.3, ci_high=0.1, inconclusive=0,
                          status="INCONCLUSIVE", n_usable=1)
    r = diff_report(v, targets=["x"], selective_calls=0, full_estimate=4, min_samples=3)
    assert "too few usable trajectories" in r


def test_attribution_shown_only_when_it_adds_info():
    # attribution names the same single target → suppressed
    same = RegressionVerdict(workflow_id="w", mode="selective", n_trajectories=4, regressed=True,
                             magnitude=-0.7, ci_low=-0.9, ci_high=-0.4,
                             attribution=[("responder", -0.7)], status="FAIL", n_usable=4)
    assert "attribution:" not in diff_report(same, ["responder"], 4, 12)
    # attribution names a different node → shown
    diff = RegressionVerdict(workflow_id="w", mode="selective", n_trajectories=4, regressed=True,
                             magnitude=-0.7, ci_low=-0.9, ci_high=-0.4,
                             attribution=[("planner", -0.5)], status="FAIL", n_usable=4)
    assert "attribution:" in diff_report(diff, ["responder"], 4, 12)
