"""Immutable fleet inventory and its canonical-shape validation (FR-1, NFR-1)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from gpu_lab_twin.domain.errors import InventoryError

NODE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")

WORKSTATION_COUNT = 31
SERVER_COUNT = 1
WORKSTATION_GPU_VRAM_GB = 24
SERVER_GPU_VRAM_GB = 48
SERVER_GPU_COUNT = 2
WORKSTATION_STORAGE_GB = 500
SERVER_STORAGE_GB = 4000
TOTAL_NODES = WORKSTATION_COUNT + SERVER_COUNT
TOTAL_GPUS = WORKSTATION_COUNT + SERVER_GPU_COUNT
TOTAL_VRAM_GB = WORKSTATION_COUNT * WORKSTATION_GPU_VRAM_GB + SERVER_GPU_COUNT * SERVER_GPU_VRAM_GB


class NodeKind(StrEnum):
    WORKSTATION = "WORKSTATION"
    SERVER = "SERVER"


@dataclass(frozen=True, slots=True)
class GpuDeviceSpec:
    gpu_device_id: str
    ordinal: int
    vram_capacity_gb: int


@dataclass(frozen=True, slots=True)
class NodeSpec:
    node_id: str
    kind: NodeKind
    heartbeat_interval_ms: int
    storage_capacity_gb: int
    gpu_devices: tuple[GpuDeviceSpec, ...]

    def gpu(self, gpu_device_id: str) -> GpuDeviceSpec | None:
        return next((gpu for gpu in self.gpu_devices if gpu.gpu_device_id == gpu_device_id), None)


@dataclass(frozen=True, slots=True)
class FleetInventory:
    """The run's fixed topology. Construct only through :meth:`validated`."""

    nodes: tuple[NodeSpec, ...]

    @classmethod
    def validated(cls, nodes: Iterable[NodeSpec]) -> FleetInventory:
        inventory = cls(tuple(nodes))
        inventory._validate()
        return inventory

    def node(self, node_id: str) -> NodeSpec | None:
        return next((node for node in self.nodes if node.node_id == node_id), None)

    @property
    def gpu_count(self) -> int:
        return sum(len(node.gpu_devices) for node in self.nodes)

    @property
    def total_vram_gb(self) -> int:
        return sum(gpu.vram_capacity_gb for node in self.nodes for gpu in node.gpu_devices)

    def _validate(self) -> None:
        node_ids = [node.node_id for node in self.nodes]
        if len(set(node_ids)) != len(node_ids):
            raise InventoryError("node IDs must be unique")
        gpu_ids = [gpu.gpu_device_id for node in self.nodes for gpu in node.gpu_devices]
        if len(set(gpu_ids)) != len(gpu_ids):
            raise InventoryError("GPU device IDs must be unique across the fleet")

        for node in self.nodes:
            _validate_node(node)

        workstations = [n for n in self.nodes if n.kind is NodeKind.WORKSTATION]
        servers = [n for n in self.nodes if n.kind is NodeKind.SERVER]
        if len(workstations) != WORKSTATION_COUNT or len(servers) != SERVER_COUNT:
            raise InventoryError(
                f"expected {WORKSTATION_COUNT} workstations and {SERVER_COUNT} server, "
                f"got {len(workstations)} and {len(servers)}"
            )
        if self.gpu_count != TOTAL_GPUS or self.total_vram_gb != TOTAL_VRAM_GB:
            raise InventoryError(
                f"expected {TOTAL_GPUS} GPUs / {TOTAL_VRAM_GB} GB VRAM, got {self.gpu_count} / {self.total_vram_gb} GB"
            )


def _validate_node(node: NodeSpec) -> None:
    if not NODE_ID_PATTERN.fullmatch(node.node_id):
        raise InventoryError(f"node ID {node.node_id!r} violates {NODE_ID_PATTERN.pattern}")
    if node.heartbeat_interval_ms <= 0:
        raise InventoryError(f"{node.node_id}: heartbeat interval must be positive")

    if node.kind is NodeKind.WORKSTATION:
        expected_gpus, expected_vram, expected_storage = 1, WORKSTATION_GPU_VRAM_GB, WORKSTATION_STORAGE_GB
    else:
        expected_gpus, expected_vram, expected_storage = SERVER_GPU_COUNT, SERVER_GPU_VRAM_GB, SERVER_STORAGE_GB

    if len(node.gpu_devices) != expected_gpus:
        raise InventoryError(f"{node.node_id}: expected {expected_gpus} GPU(s), got {len(node.gpu_devices)}")
    if any(gpu.vram_capacity_gb != expected_vram for gpu in node.gpu_devices):
        raise InventoryError(f"{node.node_id}: every GPU must have {expected_vram} GB VRAM")
    if sorted(gpu.ordinal for gpu in node.gpu_devices) != list(range(expected_gpus)):
        raise InventoryError(f"{node.node_id}: GPU ordinals must be 0..{expected_gpus - 1}")
    if node.storage_capacity_gb != expected_storage:
        raise InventoryError(f"{node.node_id}: expected {expected_storage} GB storage")
