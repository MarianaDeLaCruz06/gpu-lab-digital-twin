from datetime import timedelta

from fastapi.testclient import TestClient

from gpu_lab_twin.bootstrap import Container
from gpu_lab_twin.adapters.sim.fake_clock import FakeClock
from tests.conftest import T0
from tests.support import heartbeat_body


def test_canonical_route_feeds_bounded_peak_projection(
    client: TestClient, container: Container, fake_clock: FakeClock
) -> None:
    temperatures = (40.0, 81.0, 50.0)
    for sequence, temperature in enumerate(temperatures, start=1):
        fake_clock.advance(seconds=0.02)
        at = T0 + timedelta(milliseconds=sequence * 20)
        response = client.post(
            "/v1/nodes/ws-gpu-01/heartbeats",
            json=heartbeat_body("ws-gpu-01", at, seq=sequence, temperatures=(temperature,)),
        )
        assert response.status_code == 200
        assert response.json()["outcome"] == "APPLIED"

    windows = container.telemetry.windows("ws-gpu-01")
    assert len(windows) == 1
    assert windows[0].samples_seen == 3
    assert windows[0].gpus[0].peak_temperature_c == 81.0


def test_burst_across_all_nodes_retains_every_heartbeat_semantic(
    client: TestClient, container: Container, fake_clock: FakeClock
) -> None:
    for index, spec in enumerate(container.inventory.nodes, start=1):
        fake_clock.advance(seconds=0.001)
        temperatures = tuple(45.0 for _ in spec.gpu_devices)
        at = T0 + timedelta(milliseconds=index)
        response = client.post(
            f"/v1/nodes/{spec.node_id}/heartbeats",
            json=heartbeat_body(spec.node_id, at, seq=1, temperatures=temperatures, vram_gb=tuple(0.0 for _ in temperatures)),
        )
        assert response.status_code == 200
        assert response.json()["outcome"] == "APPLIED"

    fleet = client.get("/v1/nodes").json()
    assert fleet["nodeCount"] == 32
    assert all(node["nodeRevision"] == 1 for node in fleet["nodes"])
    assert container.telemetry.retained_windows == 32
