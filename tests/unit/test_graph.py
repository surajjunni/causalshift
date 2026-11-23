import pytest

from causalshift.graph.dag import DependencyGraph
from causalshift.models import Workflow


def _g(edges):
    return DependencyGraph(Workflow("w", ["root", "mid", "side", "leaf"], edges))


EDGES = [("root", "mid"), ("mid", "leaf"), ("root", "side")]


def test_affected_set_midfault_includes_leaf():
    assert _g(EDGES).affected_set(["mid"]) == {"mid", "leaf"}


def test_affected_set_sidefault_excludes_leaf():
    # side has no declared child → leaf is NOT in the declared affected set
    assert _g(EDGES).affected_set(["side"]) == {"side"}


def test_affected_set_root_is_everything():
    assert _g(EDGES).affected_set(["root"]) == {"root", "mid", "side", "leaf"}


def test_unknown_target_errors():
    with pytest.raises(ValueError):
        _g(EDGES).affected_set(["nope"])
