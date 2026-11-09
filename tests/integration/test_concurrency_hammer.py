"""Concurrency hammers (Impl-2 checklist: "Concurrency Defense").

Each test fires simultaneous HTTP requests through the real FastAPI app, repository adapter and database,
then proves from database state that no race produced a double allocation, a lost update or a 5xx.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from gpu_lab_twin.adapters.db.models import MaintenanceLockRow, NodeRow, TelemetrySnapshotRow
from gpu_lab_twin.bootstrap import Container
from tests.conftest import T0
from tests.support import heartbeat_body

SERVER = "central-gpu-server"
WORKERS = 16


def _hammer(client: TestClient, requests: list[tuple[str, dict[str, Any]]]) -> list[tuple[int, dict[str, Any]]]:
    """Release every request at the same instant (barrier) and collect (status, body) pairs."""
    start = Barrier(len(requests))

    def fire(request: tuple[str, dict[str, Any]]) -> tuple[int, dict[str, Any]]:
        path, body = request
        start.wait()
        response = client.post(path, json=body)
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=len(requests)) as executor:
        return list(executor.map(fire, requests))


def _server_heartbeat(seq: int = 1) -> dict[str, Any]:
    return heartbeat_body(SERVER, T0, seq=seq, temperatures=(45.0, 46.0), vram_gb=(1.0, 1.0))


def _drain_request(index: int, revision: int) -> dict[str, Any]:
    return {
        "eventId": str(uuid5(NAMESPACE_URL, f"hammer-drain-event-{index}")),
        "requestId": str(uuid5(NAMESPACE_URL, f"hammer-drain-request-{index}")),
        "occurredAt": T0.isoformat(),
        "schemaVersion": "1.0",
        "startsAt": T0.isoformat(),
        "reason": f"Technician {index} maintenance",
        "expectedNodeRevision": revision,
        "actor": f"technician-{index}",
    }


def test_simultaneous_drain_requests_allocate_exactly_one_maintenance_lock(
    client: TestClient, container: Container
) -> None:
    assert client.post(f"/v1/nodes/{SERVER}/heartbeats", json=_server_heartbeat()).status_code == 200
    revision = container.nodes.get_node(SERVER).revision

    results = _hammer(
        client, [(f"/v1/nodes/{SERVER}/maintenance-drains", _drain_request(i, revision)) for i in range(WORKERS)]
    )

    statuses = [status for status, _ in results]
    assert statuses.count(201) == 1, statuses
    assert statuses.count(409) == WORKERS - 1, statuses
    assert {body["code"] for status, body in results if status == 409} <= {
        "ERR_MAINTENANCE_CONFLICT",
        "ERR_REVISION_CONFLICT",
    }
    winner = next(body for status, body in results if status == 201)
    assert winner["state"] == "DRAINING"
    assert winner["cordoned"] is True
    with container.engine.connect() as connection:
        locks = connection.scalar(
            select(func.count()).select_from(MaintenanceLockRow).where(MaintenanceLockRow.node_id == SERVER)
        )
        node_revision = connection.scalar(select(NodeRow.revision).where(NodeRow.node_id == SERVER))
    assert locks == 1
    assert container.nodes.count_active_maintenance_locks(SERVER) == 1
    assert node_revision == revision + 1, "only the winning drain may advance the revision"


def test_simultaneous_replays_of_one_heartbeat_apply_it_exactly_once(client: TestClient, container: Container) -> None:
    body = _server_heartbeat()

    results = _hammer(client, [(f"/v1/nodes/{SERVER}/heartbeats", body)] * WORKERS)

    outcomes = [response["outcome"] for status, response in results if status == 200]
    assert len(outcomes) == WORKERS, [status for status, _ in results]
    assert outcomes.count("APPLIED") == 1
    assert outcomes.count("DUPLICATE") == WORKERS - 1
    with container.engine.connect() as connection:
        stored = connection.scalar(
            select(func.count())
            .select_from(TelemetrySnapshotRow)
            .where(TelemetrySnapshotRow.event_id == UUID(body["eventId"]))
        )
    assert stored == 1
    assert container.nodes.get_node(SERVER).revision == 1


def test_whole_fleet_burst_keeps_one_gapless_global_ingest_order(client: TestClient, container: Container) -> None:
    """Every node reports at once, three times each: offsets stay unique and gapless (AD-1), no update is lost."""
    requests = []
    for spec in container.inventory.nodes:
        gpus = len(spec.gpu_devices)
        for seq in (1, 2, 3):
            occurred = T0 - timedelta(seconds=3 - seq)  # later sequence = later sample
            body = heartbeat_body(spec.node_id, occurred, seq=seq, temperatures=(50.0,) * gpus, vram_gb=(2.0,) * gpus)
            requests.append((f"/v1/nodes/{spec.node_id}/heartbeats", body))

    results = _hammer(client, requests)

    assert all(status == 200 for status, _ in results), sorted({status for status, _ in results})
    outcomes = {response["outcome"] for _, response in results}
    assert outcomes <= {"APPLIED", "LATE_IGNORED"}
    with container.engine.connect() as connection:
        offsets = connection.scalars(select(TelemetrySnapshotRow.ingest_offset)).all()
    assert len(offsets) == len(requests)
    assert sorted(offsets) == list(range(min(offsets), min(offsets) + len(requests))), "ingest offsets must be gapless"
    for spec in container.inventory.nodes:
        node = container.nodes.get_node(spec.node_id)
        # Whatever the interleaving, the newest sequence wins and nothing applies twice.
        assert node.current_source_sequence == 3, spec.node_id
        assert 1 <= node.revision <= 3, spec.node_id
