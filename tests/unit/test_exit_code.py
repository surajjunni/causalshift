"""Fail-closed CI semantics: inconclusive is never a pass (review finding #1)."""

from replaygate.models import RegressionVerdict
from replaygate.report.verdict import verdict_exit_code


def _v(regressed, inconclusive):
    return RegressionVerdict(workflow_id="w", mode="selective", n_trajectories=5,
                             regressed=regressed, magnitude=0.0, ci_low=0.0, ci_high=0.0,
                             inconclusive=inconclusive)


def test_clean_no_regression_passes():
    assert verdict_exit_code(_v(False, 0)) == 0


def test_regression_fails():
    assert verdict_exit_code(_v(True, 0)) == 1


def test_inconclusive_fails_closed_even_if_not_regressed():
    # the dangerous case: not 'regressed', but we could not establish it → must NOT exit 0
    assert verdict_exit_code(_v(False, 2)) == 2


def test_inconclusive_fails_closed_even_if_regressed():
    assert verdict_exit_code(_v(True, 1)) == 2
