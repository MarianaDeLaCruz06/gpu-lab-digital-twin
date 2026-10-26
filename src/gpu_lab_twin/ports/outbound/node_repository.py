from __future__ import annotations

from typing import Protocol

from gpu_lab_twin.domain.fleet import FleetInventory


class NodeRepository(Protocol):
    """Persistence for the node aggregates of one simulation run."""

    def seed_inventory(self, inventory: FleetInventory) -> int:
        """Insert configured nodes/GPUs that are not yet stored; return how many nodes were added."""
        ...

    def count_nodes(self) -> int: ...

    def count_gpu_devices(self) -> int: ...
