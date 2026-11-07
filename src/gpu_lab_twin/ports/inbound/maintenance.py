from __future__ import annotations

from typing import Protocol

from gpu_lab_twin.domain.maintenance import MaintenanceResult, MaintenanceWindow, WorkloadSnapshot


class MaintenancePort(Protocol):
    def schedule(self, node_id: str, window: MaintenanceWindow) -> MaintenanceResult: ...

    def submit_workload(self, snapshot: WorkloadSnapshot) -> MaintenanceResult: ...
