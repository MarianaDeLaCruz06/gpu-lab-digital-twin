"""AD-1: node writes are compare-and-swap on the revision; a stale writer commits nothing."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from gpu_lab_twin.bootstrap import Container
from tests.conftest import T0
from tests.support import assert_matches_contract, effect_probe, heartbeat_body


def test_writer_holding_a_stale_revision_gets_409_and_writes_nothing(
    client: TestClient, container: Container, fake_clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.post("/v1/nodes/ws-gpu-11/heartbeats", json=heartbeat_body("ws-gpu-11", T0))
    stale = replace(container.nodes.get_node("ws-gpu-11"), revision=0)
    monkeypatch.setattr(container.nodes, "get_node", lambda node_id: stale)
    before = effect_probe(container.engine)

    later = fake_clock.advance(seconds=10)
    response = client.post("/v1/nodes/ws-gpu-11/heartbeats", json=heartbeat_body("ws-gpu-11", later, seq=2))

    assert response.status_code == 409
    body = response.json()
    assert_matches_contract("ErrorBody", body)
    assert (body["code"], body["retryable"], body["details"]) == (
        "ERR_REVISION_CONFLICT",
        True,
        {"expected": 0, "actual": 1},
    )
    assert effect_probe(container.engine) == before
