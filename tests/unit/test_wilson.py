"""Wilson score interval for the missed-regression rate (review #3)."""

from causalshift.evaluate.population import wilson_interval


def test_empty_is_zero():
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_zero_events_lower_is_zero_upper_positive():
    lo, hi = wilson_interval(0, 20)
    assert lo == 0.0 and 0.0 < hi < 0.2       # not a false certainty of 0 risk


def test_all_events_upper_is_one():
    lo, hi = wilson_interval(20, 20)
    assert hi == 1.0 and lo < 1.0


def test_interval_brackets_the_point_estimate():
    for k, n in [(1, 31), (3, 40), (5, 20), (0, 10), (10, 10)]:
        lo, hi = wilson_interval(k, n)
        assert lo <= k / n <= hi
        assert 0.0 <= lo <= hi <= 1.0


def test_small_sample_interval_is_wide():
    # one event out of a few: the interval must be honestly wide, not ~0
    lo, hi = wilson_interval(1, 5)
    assert hi - lo > 0.3
