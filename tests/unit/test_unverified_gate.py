"""Fail closed on unverified dependencies: a selective-replay PASS on an 'unverified'
capture is downgraded to INCONCLUSIVE unless the user accepts the risk."""

from replaygate.models import RegressionVerdict
from replaygate.report.verdict import gate_unverified_dependencies, verdict_exit_code


def _pass(mode="selective"):
    return RegressionVerdict(workflow_id="w", mode=mode, n_trajectories=5, regressed=False,
                             magnitude=0.0, ci_low=0.0, ci_high=0.1, status="PASS", n_usable=5)


def test_unverified_selective_pass_is_downgraded():
    v = _pass()
    assert gate_unverified_dependencies(v, "unverified") is True
    assert v.status == "INCONCLUSIVE"
    assert verdict_exit_code(v) == 2


def test_accept_flag_keeps_pass():
    v = _pass()
    assert gate_unverified_dependencies(v, "unverified", accept=True) is False
    assert v.status == "PASS"


def test_declared_coverage_keeps_pass():
    v = _pass()
    assert gate_unverified_dependencies(v, "declared") is False
    assert v.status == "PASS"


def test_full_mode_pass_not_downgraded():
    # full re-execution did not reuse anything, so dependency completeness is moot
    v = _pass(mode="full")
    assert gate_unverified_dependencies(v, "unverified") is False
    assert v.status == "PASS"


def test_fail_is_not_affected():
    v = RegressionVerdict(workflow_id="w", mode="selective", n_trajectories=5, regressed=True,
                          magnitude=-0.7, ci_low=-0.9, ci_high=-0.5, status="FAIL", n_usable=5)
    assert gate_unverified_dependencies(v, "unverified") is False
    assert v.status == "FAIL"
