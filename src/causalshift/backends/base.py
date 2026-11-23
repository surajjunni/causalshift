"""Recompute backend contract (contracts/recompute-backend.md).

The backend recomputes a node under an intervention, given the CURRENT output of
every node. A backend may read whatever true inputs it needs from current_outputs
— modeling that the real agent's node reads its real inputs, which the tool's
declared graph may describe incompletely. Ordinary unavailability returns
Unavailable (never raises); an un-recomputable affected node makes the verdict
inconclusive, never "safe"."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Union, runtime_checkable

from causalshift.models import Cost


@dataclass
class Produced:
    output: str
    cost: Cost


@dataclass
class Unavailable:
    reason: str


Outcome = Union[Produced, Unavailable]


@runtime_checkable
class RecomputeBackend(Protocol):
    def recompute(
        self,
        node_name: str,
        model_id: str,
        prompt_id: str,
        current_outputs: dict[str, str],
        predecessors: Optional[list[str]] = None,
    ) -> Outcome:
        ...


class UnavailableBackend:
    """Default offline backend: cannot recompute anything."""
    name = "unavailable"

    def recompute(self, node_name, model_id, prompt_id, current_outputs,
                  predecessors=None) -> Outcome:
        return Unavailable("no recompute backend configured")
