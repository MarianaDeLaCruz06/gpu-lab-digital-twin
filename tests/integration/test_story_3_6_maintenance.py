from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from fastapi.testclient import TestClient

from gpu_lab_twin.adapters.sim.fake_clock import FakeClock
from gpu_lab_twin.bootstrap import Container
from tests.conftest import T0
from tests.support import heartbeat_body

NODE_ID = "central-gpu-server"


def _schedule_body(*, revision: int = 1, reason: str = "Planned lab maintenance") -> dict:
    request_id = uuid5(NAMESPACE_URL, "story-3.6-maintenance-request")
    return {
        "eventId": str(uuid5(NAMESPACE_URL, "story-3.6-maintenance-event")),
        "requestId": str(request_id),
        "occurredAt": T0.isoformat(),
        "schemaVersion": "1.0",
        "startsAt": T0.isoformat(),
        "reason": reason,
        "expectedNodeRevision": revision,
        "actor": "Carlos",
    }


def _healthy_server(client: TestClient) -> None:
    response = client.post(
        f"/v1/nodes/{NODE_ID}/heartbeats",
        json=heartbeat_body(NODE_ID, T0, temperatures=(45.0, 46.0), vram_gb=(1.0, 1.0)),
    )
    assert response.status_code == 200
    assert response.json()["state"] == "HEALTHY"


def test_schedule_replay_and_fresh_zero_complete_canonical_drain(
    client: TestClient, container: Container, fake_clock: FakeClock
) -> None:
    _healthy_server(client)
    body = _schedule_body()
    scheduled = client.post(f"/v1/nodes/{NODE_ID}/maintenance-drains", json=body)
    assert scheduled.status_code == 201
    assert scheduled.json()["state"] == "DRAINING"
    assert scheduled.json()["cordoned"] is True
    assert container.nodes.count_active_maintenance_locks(NODE_ID) == 1

    replay = client.post(f"/v1/nodes/{NODE_ID}/maintenance-drains", json=body)
    assert replay.status_code == 200
    assert replay.json()["outcome"] == "DUPLICATE"
    assert replay.json()["lockId"] == scheduled.json()["lockId"]
    assert container.nodes.count_active_maintenance_locks(NODE_ID) == 1

    fake_clock.advance(seconds=1)
    workload = {
        "eventId": str(uuid5(NAMESPACE_URL, "story-3.6-workload-zero-event")),
        "snapshotId": str(uuid5(NAMESPACE_URL, "story-3.6-workload-zero-snapshot")),
        "nodeId": NODE_ID,
        "source": "EXTERNAL_MOCK",
        "sourceRevision": 2,
        "observedAt": (T0 + timedelta(seconds=1)).isoformat(),
        "receivedAt": (T0 + timedelta(seconds=1)).isoformat(),
        "activeWorkloadCount": 0,
        "activeWorkloadIds": [],
    }
    completed = client.post("/v1/fixtures/workload-snapshots", json=workload)
    assert completed.status_code == 200
    assert completed.json()["state"] == "MAINTENANCE"
    assert completed.json()["cordoned"] is True
    node = next(item for item in client.get("/v1/nodes").json()["nodes"] if item["nodeId"] == NODE_ID)
    assert node["state"] == "MAINTENANCE"
    assert node["cordoned"] is True


def test_changed_replay_is_typed_idempotency_conflict(client: TestClient) -> None:
    _healthy_server(client)
    body = _schedule_body()
    assert client.post(f"/v1/nodes/{NODE_ID}/maintenance-drains", json=body).status_code == 201
    changed = body | {"reason": "Different request body"}
    conflict = client.post(f"/v1/nodes/{NODE_ID}/maintenance-drains", json=changed)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "ERR_IDEMPOTENCY_CONFLICT"
