"""P1: the false-negative sweep varies topology × hidden-edge frequency and the
rate scales with hidden-edge frequency (measured vs independent ground truth)."""

from benchmark.faults.inject import TOPOLOGIES
from benchmark.sweep import HIDDEN_FRACTIONS, sweep


def test_sweep_covers_topologies_and_frequencies():
    rows = sweep(n_reg=20, n_nonreg=4, m=12, seed=7)
    assert len(rows) == len(TOPOLOGIES) * len(HIDDEN_FRACTIONS)
    assert {r["topology"] for r in rows} == {t.name for t in TOPOLOGIES}


def test_false_negatives_scale_with_hidden_edge_frequency():
    rows = sweep(n_reg=20, n_nonreg=4, m=12, seed=7)
    for topo in {r["topology"] for r in rows}:
        by_hf = {r["hidden_fraction"]: r for r in rows if r["topology"] == topo}
        assert by_hf[0.0]["false_negative"] == 0.0        # no hidden edges → no misses
        assert by_hf[0.5]["false_negative"] > 0.2         # many hidden edges → many misses
        assert by_hf[0.5]["false_negative"] >= by_hf[0.1]["false_negative"]  # monotone-ish


def test_full_is_a_sound_oracle_on_these_topologies():
    rows = sweep(n_reg=20, n_nonreg=4, m=12, seed=7)
    assert all(r["full_missed"] == 0.0 for r in rows)     # full catches every true regression
