"""T033: the gate must bite — an all-missing-edge corpus drives false negatives
up and fails the gate; a normal corpus passes."""

from benchmark.faults.inject import make_corpus
from benchmark.run_benchmark import SC, _gate, run


def test_normal_corpus_passes_gate():
    rep = run(make_corpus(n_normal=20, n_missing=1, n_nonreg=5, m_trajectories=20))
    assert rep.missed_regressions <= SC["false_neg"]
    assert _gate(rep) is True
    assert rep.call_ratio < 1.0            # selective is cheaper than full


def test_unsound_corpus_fails_gate():
    # every case is a hidden-edge regression selective cannot catch → FN high
    rep = run(make_corpus(n_normal=0, n_missing=8, n_nonreg=0, m_trajectories=20))
    assert rep.missed_regressions > SC["false_neg"]
    assert _gate(rep) is False
