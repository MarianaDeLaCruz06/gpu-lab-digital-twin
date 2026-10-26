"""Loads the canonical simulated fleet from fixtures/fleet.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gpu_lab_twin.domain.errors import InventoryError
from gpu_lab_twin.domain.fleet import FleetInventory, GpuDeviceSpec, NodeKind, NodeSpec


def load_fleet_inventory(path: Path) -> FleetInventory:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        nodes = [_node_from_json(raw) for raw in document["nodes"]]
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise InventoryError(f"cannot read fleet fixture {path}: {exc}") from exc
    return FleetInventory.validated(nodes)


def _node_from_json(raw: dict[str, Any]) -> NodeSpec:
    return NodeSpec(
        node_id=raw["nodeId"],
        kind=NodeKind(raw["kind"]),
        heartbeat_interval_ms=int(raw["heartbeatIntervalMs"]),
        storage_capacity_gb=int(raw["storageCapacityGb"]),
        gpu_devices=tuple(
            GpuDeviceSpec(
                gpu_device_id=gpu["gpuDeviceId"],
                ordinal=int(gpu["ordinal"]),
                vram_capacity_gb=int(gpu["vramCapacityGb"]),
            )
            for gpu in raw["gpuDevices"]
        ),
    )
