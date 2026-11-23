import pytest

from causalshift.models import Cost, Step, Trajectory, Workflow
from causalshift.store.validate import TraceInputError, validate_workflow


def _wf(edges, steps_fp="fp"):
    steps = [Step(0, "a", steps_fp, "1", "A", "p"), Step(1, "b", steps_fp, "2", "A", "p")]
    t = Trajectory("t0", "w", steps)
    return Workflow("w", ["a", "b"], edges, [t])


def test_valid_dag_accepted():
    validate_workflow(_wf([("a", "b")]))


def test_cyclic_rejected():
    with pytest.raises(TraceInputError, match="cyclic"):
        validate_workflow(_wf([("a", "b"), ("b", "a")]))


def test_undeclared_edge_node_rejected():
    with pytest.raises(TraceInputError, match="undeclared"):
        validate_workflow(_wf([("a", "z")]))


def test_missing_fingerprint_rejected():
    with pytest.raises(TraceInputError, match="input_fingerprint"):
        validate_workflow(_wf([("a", "b")], steps_fp=""))
