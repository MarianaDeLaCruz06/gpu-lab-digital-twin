"""Story 1.1: GET /v1/nodes returns the complete fleet; missing telemetry is null, never zero."""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import delete

from gpu_lab_twin.adapters.db.models import GpuDeviceRow, NodeRow
from gpu_lab_twin.bootstrap import Container
from tests.conftest import T0
from tests.support import assert_matches_contract, heartbeat_body


def test_fleet_lists_all_32_nodes_once_in_inventory_order(client: TestClient) -> None:
    response = client.get("/v1/nodes")

    assert response.status_code == 200
    body = response.json()
    assert_matches_contract("FleetResponse", body)
    node_ids = [node["nodeId"] for node in body["nodes"]]
    assert node_ids == [f"ws-gpu-{i:02d}" for i in range(1, 32)] + ["central-gpu-server"]
    assert sum(len(node["gpus"]) for node in body["nodes"]) == 33
    assert {node["storageCapacityGb"] for node in body["nodes"][:31]} == {500}
    assert body["nodes"][-1]["storageCapacityGb"] == 4000


def test_nodes_without_telemetry_show_null_readings_and_stay_cordoned(client: TestClient) -> None:
    server = client.get("/v1/nodes").json()["nodes"][-1]

    assert (server["state"], server["cordoned"], server["connectivityStatus"]) == ("UNKNOWN", True, "UNKNOWN")
    assert server["lastHeartbeatReceivedAt"] is None
    assert server["storageFreeGb"] is None
    assert [(g["temperatureC"], g["vramOccupiedGb"]) for g in server["gpus"]] == [(None, None), (None, None)]


def test_fleet_reflects_an_ingested_heartbeat(client: TestClient) -> None:
    client.post(
        "/v1/nodes/central-gpu-server/heartbeats",
        json=heartbeat_body("central-gpu-server", T0, temperatures=(61.5, 63.0), vram_gb=(30.0, 0.0)),
    )

    server = client.get("/v1/nodes").json()["nodes"][-1]

    assert (server["state"], server["cordoned"], server["nodeRevision"]) == ("HEALTHY", False, 1)
    assert datetime.fromisoformat(server["lastHeartbeatReceivedAt"]) == T0
    assert server["storageFreeGb"] == 320.0
    assert [(g["gpuDeviceId"], g["temperatureC"], g["vramOccupiedGb"]) for g in server["gpus"]] == [
        ("central-gpu-server-gpu-0", 61.5, 30.0),
        ("central-gpu-server-gpu-1", 63.0, 0.0),
    ]


def test_fleet_diverging_from_the_inventory_fails_closed(client: TestClient, container: Container) -> None:
    with container.engine.begin() as connection:
        connection.execute(delete(GpuDeviceRow).where(GpuDeviceRow.node_id == "ws-gpu-31"))
        connection.execute(delete(NodeRow).where(NodeRow.node_id == "ws-gpu-31"))

    response = client.get("/v1/nodes")

    assert response.status_code == 503
    body = response.json()
    assert_matches_contract("ErrorBody", body)
    assert (body["code"], body["details"]["missingNodeIds"]) == ("ERR_INGRESS_UNAVAILABLE", ["ws-gpu-31"])
