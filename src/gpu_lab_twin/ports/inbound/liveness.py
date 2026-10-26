from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LivenessReport:
    evaluated_at: datetime
    transitioned_node_ids: tuple[str, ...]
    held_node_ids: tuple[str, ...]
    failed_node_ids: tuple[str, ...] = ()


class LivenessPort(Protocol):
    """`evaluate_fleet_liveness`: one ordered clock evaluation of AD-2 silence across the fleet."""

    def evaluate_fleet_liveness(self, evaluation_at: datetime | None = None) -> LivenessReport: ...
