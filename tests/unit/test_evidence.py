"""P0: insufficient statistical evidence must fail closed (never a silent PASS)."""

from causalshift.models import ReplayResult
from causalshift.report.verdict import build_verdict, verdict_exit_code


def _r(delta, inconclusive=False):
    return ReplayResult(trajectory_id="t", mode="selective", decisions=[],
                        candidate_outputs={}, quality_score=1.0 + delta,
                        baseline_score=1.0, calls=0, tokens=0, latency_ms=0.0,
                        inconclusive=inconclusive)


def test_empty_results_is_inconclusive_not_pass():
    v = build_verdict("w", "selective", [])
    assert v.status == "INCONCLUSIVE"
    assert verdict_exit_code(v) == 2          # was the fail-open hole → now exit 2


def test_too_few_usable_is_inconclusive():
    v = build_verdict("w", "selective", [_r(0.0), _r(0.0)], min_samples=3)
    assert v.n_usable == 2 and v.status == "INCONCLUSIVE"
    assert verdict_exit_code(v) == 2


def test_enough_evidence_no_regression_passes():
    v = build_verdict("w", "selective", [_r(0.0) for _ in range(5)], min_samples=3)
    assert v.status == "PASS" and verdict_exit_code(v) == 0


def test_enough_evidence_clear_regression_fails():
    v = build_verdict("w", "selective", [_r(-1.0) for _ in range(5)], min_samples=3)
    assert v.status == "FAIL" and verdict_exit_code(v) == 1


def test_all_inconclusive_fails_closed_even_with_many():
    v = build_verdict("w", "selective", [_r(0.0, inconclusive=True) for _ in range(9)])
    assert v.n_usable == 0 and v.status == "INCONCLUSIVE"
    assert verdict_exit_code(v) == 2


def test_non_inferiority_margin_straddle_is_not_pass():
    # a high-variance CI crossing the -epsilon margin must NOT be a silent PASS
    deltas = [_r(d) for d in (-0.6, -0.6, -0.6, 0.4, 0.4)]
    v = build_verdict("w", "selective", deltas, min_samples=3, epsilon=0.2)
    assert v.status in ("INCONCLUSIVE", "FAIL")
    assert verdict_exit_code(v) != 0
