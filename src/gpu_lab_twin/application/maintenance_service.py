from __future__ import annotations

import threading

from gpu_lab_twin.domain.errors import DomainError, ErrorCode
from gpu_lab_twin.domain.fleet import FleetInventory
from gpu_lab_twin.domain.maintenance import MaintenanceResult, MaintenanceWindow, WorkloadSnapshot
from gpu_lab_twin.ports.outbound.clock import Clock
from gpu_lab_twin.ports.outbound.node_repository import NodeRepository


class MaintenanceService:
    def __init__(self, *, inventory: FleetInventory, nodes: NodeRepository, clock: Clock, write_lock: threading.Lock) -> None:
        self._inventory = inventory
        self._nodes = nodes
        self._clock = clock
        self._write_lock = write_lock

    def schedule(self, node_id: str, window: MaintenanceWindow) -> MaintenanceResult:
        if self._inventory.node(node_id) is None:
            raise DomainError(ErrorCode.ERR_UNKNOWN_NODE, f"Node {node_id} is not configured in this simulation run.")
        with self._write_lock:
            return self._nodes.schedule_maintenance(node_id, window, self._clock.now())

    def submit_workload(self, snapshot: WorkloadSnapshot) -> MaintenanceResult:
        if self._inventory.node(snapshot.node_id) is None:
            raise DomainError(
                ErrorCode.ERR_UNKNOWN_NODE, f"Node {snapshot.node_id} is not configured in this simulation run."
            )
        with self._write_lock:
            return self._nodes.apply_workload_snapshot(snapshot, self._clock.now())
