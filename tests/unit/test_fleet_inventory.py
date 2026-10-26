from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from gpu_lab_twin.adapters.sim.fleet_fixture import load_fleet_inventory
from gpu_lab_twin.domain.errors import InventoryError
from gpu_lab_twin.domain.fleet import FleetInventory, GpuDeviceSpec, NodeKind

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "fleet.json"


@pytest.fixture
def canonical() -> FleetInventory:
    return load_fleet_inventory(FIXTURE)


def test_canonical_fixture_has_32_nodes_33_gpus_840_gb(canonical: FleetInventory) -> None:
    workstations = [n for n in canonical.nodes if n.kind is NodeKind.WORKSTATION]
    servers = [n for n in canonical.nodes if n.kind is NodeKind.SERVER]

    assert len(canonical.nodes) == 32
    assert canonical.gpu_count == 33
    assert canonical.total_vram_gb == 840
    assert len(workstations) == 31 and all(n.storage_capacity_gb == 500 for n in workstations)
    assert [n.node_id for n in servers] == ["central-gpu-server"]
    assert servers[0].storage_capacity_gb == 4000
    assert [g.vram_capacity_gb for g in servers[0].gpu_devices] == [48, 48]


def test_duplicate_node_id_fails_closed(canonical: FleetInventory) -> None:
    nodes = list(canonical.nodes)
    nodes[1] = replace(nodes[1], node_id=nodes[0].node_id)
    with pytest.raises(InventoryError, match="unique"):
        FleetInventory.validated(nodes)


def test_missing_workstation_fails_closed(canonical: FleetInventory) -> None:
    with pytest.raises(InventoryError, match="31 workstations"):
        FleetInventory.validated(canonical.nodes[1:])


def test_wrong_vram_capacity_fails_closed(canonical: FleetInventory) -> None:
    nodes = list(canonical.nodes)
    nodes[0] = replace(nodes[0], gpu_devices=(GpuDeviceSpec(nodes[0].gpu_devices[0].gpu_device_id, 0, 48),))
    with pytest.raises(InventoryError, match="24 GB"):
        FleetInventory.validated(nodes)


def test_non_positive_heartbeat_interval_fails_closed(canonical: FleetInventory) -> None:
    nodes = list(canonical.nodes)
    nodes[3] = replace(nodes[3], heartbeat_interval_ms=0)
    with pytest.raises(InventoryError, match="interval"):
        FleetInventory.validated(nodes)


def test_unreadable_fixture_is_an_inventory_error(tmp_path: Path) -> None:
    broken = tmp_path / "fleet.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(InventoryError, match="cannot read"):
        load_fleet_inventory(broken)
