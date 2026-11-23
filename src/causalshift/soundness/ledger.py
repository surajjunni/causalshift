"""Soundness accounting (Constitution Principle I; FR-009).

At evaluate time (no ground truth) we cannot KNOW whether a reuse missed a
regression; we report the reuse fraction as a labeled UPPER BOUND on residual
risk. The true missed-regression (false-negative) rate is measured only against
ground truth, by the benchmark."""

from __future__ import annotations

from causalshift.models import REUSED, ReplayResult


def reuse_fraction(results: list[ReplayResult]) -> float:
    total = reused = 0
    for r in results:
        for d in r.decisions:
            total += 1
            if d.action == REUSED:
                reused += 1
    return reused / total if total else 0.0


def false_negative_rate(selective_regressed: list[bool], full_regressed: list[bool]) -> float:
    """Measured (benchmark): fraction of cases where selective said 'not regressed'
    but the sound full re-execution said 'regressed' — a missed regression."""
    missed = total = 0
    for sel, full in zip(selective_regressed, full_regressed):
        if full:                      # a real regression existed (per the sound oracle)
            total += 1
            if not sel:
                missed += 1
    return missed / total if total else 0.0
