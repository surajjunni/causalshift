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
