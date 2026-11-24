"""The diff risk-report formatter (offline, pure)."""

from causalshift.models import RegressionVerdict
from causalshift.report.diff import diff_report


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
    assert "PASS — no regression detected" in r
    assert "exit:         0" in r


def test_inconclusive_report_blocks():
    r = diff_report(_v(False, inconclusive=2), targets=["x"], selective_calls=0, full_estimate=8)
    assert "INCONCLUSIVE" in r and "blocks deploy" in r
    assert "exit:         2" in r
