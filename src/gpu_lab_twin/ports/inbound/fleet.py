from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from gpu_lab_twin.domain.node import NodeView


@dataclass(frozen=True, slots=True)
class FleetView:
    generated_at: datetime
    nodes: tuple[NodeView, ...]


class FleetQueryPort(Protocol):
    def list_fleet(self) -> FleetView: ...
