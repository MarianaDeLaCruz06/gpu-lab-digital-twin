from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import delete

from gpu_lab_twin.adapters.db.models import GpuDeviceRow, NodeRow
from gpu_lab_twin.bootstrap import Container


def test_liveness_reports_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_confirms_canonical_fleet_is_seeded(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "nodes": 32, "gpuDevices": 33}


def test_seeded_nodes_start_unknown_and_cordoned(client: TestClient, container: Container) -> None:
    with container.engine.connect() as connection:
        rows = connection.execute(NodeRow.__table__.select()).mappings().all()
    assert len(rows) == 32
    assert {(row["state"], row["cordoned"], row["revision"]) for row in rows} == {("UNKNOWN", True, 0)}


def test_seeding_twice_is_idempotent(client: TestClient, container: Container) -> None:
    assert container.nodes.seed_inventory(container.inventory) == 0
    assert container.nodes.count_nodes() == 32


def test_readiness_fails_with_structured_error_when_store_diverges(client: TestClient, container: Container) -> None:
    with container.engine.begin() as connection:
        connection.execute(delete(GpuDeviceRow).where(GpuDeviceRow.node_id == "ws-gpu-31"))

    response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "ERR_INGRESS_UNAVAILABLE"
    assert body["retryable"] is True
    assert body["details"]["gpuDevices"] == 32
