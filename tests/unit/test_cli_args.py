"""CLI argument validators for `diff` (margin / min-samples)."""

import argparse

import pytest

from replaygate.cli import _nonneg_float, _pos_int


def test_nonneg_float_rejects_negative_nan_and_inf():
    for bad in ("-1", "nan", "inf", "-inf"):
        with pytest.raises(argparse.ArgumentTypeError):
            _nonneg_float(bad)
    assert _nonneg_float("0") == 0.0
    assert _nonneg_float("0.2") == 0.2


def test_pos_int_requires_at_least_one():
    for bad in ("0", "-3"):
        with pytest.raises(argparse.ArgumentTypeError):
            _pos_int(bad)
    assert _pos_int("1") == 1
