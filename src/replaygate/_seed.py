"""Global seeding so benchmarks and bootstrap CIs are reproducible."""

from __future__ import annotations

import random

import numpy as np

DEFAULT_SEED = 1729


def seed_all(seed: int = DEFAULT_SEED) -> np.random.Generator:
    """Seed stdlib + numpy and return a dedicated numpy Generator."""
    random.seed(seed)
    np.random.seed(seed)
    return np.random.default_rng(seed)
