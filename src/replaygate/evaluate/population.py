"""Population-level effect with bootstrap confidence intervals (research.md)."""

from __future__ import annotations

import numpy as np


def bootstrap_mean_ci(deltas: list[float], n_boot: int = 2000,
                      alpha: float = 0.05, seed: int = 1729):
    """Return (mean, ci_low, ci_high) of the mean delta via bootstrap resampling."""
    if not deltas:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng(seed)
    arr = np.asarray(deltas, dtype=float)
    mean = float(arr.mean())
    if len(arr) == 1:
        return mean, mean, mean
    boots = rng.choice(arr, size=(n_boot, len(arr)), replace=True).mean(axis=1)
    lo = float(np.percentile(boots, 100 * alpha / 2))
    hi = float(np.percentile(boots, 100 * (1 - alpha / 2)))
    return mean, lo, hi


def is_regression(ci_high: float) -> bool:
    """Confidently worse: the whole CI of (candidate - baseline) lies below zero."""
    return ci_high < 0.0


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion k/n. The right tool
    for a RATE (e.g. missed-regression rate) with few events — unlike a bootstrap
    of the mean, it stays in [0,1] and is well-behaved at k=0 or k=n and small n.
    """
    import math
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))
