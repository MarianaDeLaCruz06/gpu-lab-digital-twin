from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from gpu_lab_twin.adapters.db.models import GpuDeviceRow, NodeRow
from gpu_lab_twin.domain.fleet import FleetInventory


class SqlNodeRepository:
    """PostgreSQL/SQLite implementation of the NodeRepository port."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def seed_inventory(self, inventory: FleetInventory) -> int:
        with self._session_factory.begin() as session:
            existing = set(session.scalars(select(NodeRow.node_id)))
            added = 0
            for spec in inventory.nodes:
                if spec.node_id in existing:
                    continue
                session.add(
                    NodeRow(
                        node_id=spec.node_id,
                        kind=spec.kind,
                        heartbeat_interval_ms=spec.heartbeat_interval_ms,
                        storage_capacity_gb=spec.storage_capacity_gb,
                        active_reason_codes=[],
                    )
                )
                session.flush()
                session.add_all(
                    GpuDeviceRow(
                        gpu_device_id=gpu.gpu_device_id,
                        node_id=spec.node_id,
                        ordinal=gpu.ordinal,
                        vram_capacity_gb=gpu.vram_capacity_gb,
                    )
                    for gpu in spec.gpu_devices
                )
                added += 1
            return added

    def count_nodes(self) -> int:
        with self._session_factory() as session:
            return session.scalar(select(func.count()).select_from(NodeRow)) or 0

    def count_gpu_devices(self) -> int:
        with self._session_factory() as session:
            return session.scalar(select(func.count()).select_from(GpuDeviceRow)) or 0
