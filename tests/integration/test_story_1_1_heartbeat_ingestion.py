"""Story 1.1 (task annex 3.1): heartbeat ingestion over POST /v1/nodes/{nodeId}/heartbeats."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from gpu_lab_twin.adapters.db.models import (
    AlertRow,
    AuditEventRow,
    NodeRow,
    NodeStateHistoryRow,
    TelemetrySnapshotRow,
)
from gpu_lab_twin.adapters.sim.fake_clock import FakeClock
from gpu_lab_twin.bootstrap import Container
from tests.conftest import T0
from tests.support import assert_matches_contract, effect_probe, heartbeat_body


def post(client: TestClient, node_id: str, body: dict):
    return client.post(f"/v1/nodes/{node_id}/heartbeats", json=body)


def node_row(container: Container, node_id: str) -> NodeRow:
    with container.engine.connect() as connection:
        return connection.execute(select(NodeRow).where(NodeRow.node_id == node_id)).one()


def assert_rejected(response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    body = response.json()
    assert body["code"] == code
    assert_matches_contract("ErrorBody", body)


# Annex scenario: Given "ws-gpu-04" is registered, When a heartbeat with 65 °C and 12288 MB VRAM arrives,
# Then the record and last_accepted_receive_at update and the contract status (200) is returned.
def test_valid_heartbeat_updates_node_and_receive_time(client: TestClient, container: Container) -> None:
    response = post(client, "ws-gpu-04", heartbeat_body("ws-gpu-04", T0, temperatures=(65.0,), vram_gb=(12.0,)))

    assert response.status_code == 200, response.text
    body = response.json()
    assert_matches_contract("IngestHeartbeatResponse", body)
    assert body["outcome"] == "APPLIED"
    assert (body["state"], body["cordoned"], body["connectivityStatus"]) == ("HEALTHY", False, "ONLINE")
    assert body["nodeRevision"] == 1
    assert datetime.fromisoformat(body["acceptedAt"]) == T0

    explanation = body["explanation"]
    assert explanation["ruleIds"] == ["HEALTHY_CURRENT_HEARTBEAT"]
    assert explanation["observedValues"]["driverHealth"] == "HEALTHY"
    assert explanation["observedValues"]["temperatureC"] == 65.0
    assert (explanation["priorState"], explanation["resultState"], explanation["expectedState"]) == (
        "UNKNOWN",
        "HEALTHY",
        "HEALTHY",
    )
    assert explanation["evidenceIds"] == [body["eventId"]]

    row = node_row(container, "ws-gpu-04")
    assert (row.state, row.cordoned, row.revision) == ("HEALTHY", False, 1)
    assert row.last_accepted_receive_at == T0


def test_state_change_writes_exactly_one_explained_history_row(
    client: TestClient, container: Container, fake_clock: FakeClock
) -> None:
    post(client, "ws-gpu-04", heartbeat_body("ws-gpu-04", T0, seq=1))
    later = fake_clock.advance(seconds=10)
    second = post(client, "ws-gpu-04", heartbeat_body("ws-gpu-04", later, seq=2))

    assert second.json()["nodeRevision"] == 2
    with container.engine.connect() as connection:
        history = connection.execute(
            select(NodeStateHistoryRow).where(NodeStateHistoryRow.node_id == "ws-gpu-04")
        ).all()
    assert len(history) == 1, "the unchanged second heartbeat must not add a transition"
    assert history[0].node_revision == 1
    assert history[0].rule_ids and history[0].evidence_ids
    assert node_row(container, "ws-gpu-04").last_accepted_receive_at == later


def test_unknown_node_is_404_with_zero_effects(client: TestClient, container: Container) -> None:
    before = effect_probe(container.engine)
    assert_rejected(post(client, "ws-gpu-99", heartbeat_body("ws-gpu-99", T0)), 404, "ERR_UNKNOWN_NODE")
    assert effect_probe(container.engine) == before


@pytest.mark.parametrize(
    ("node_id", "mutate"),
    [
        ("WS_BAD", lambda body: body),
        ("ws-gpu-04", lambda body: body.pop("driverHealth") and body),
        ("ws-gpu-04", lambda body: {**body, "currentState": "HEALTHY"}),
        ("ws-gpu-04", lambda body: {**body, "driverHealth": "FLAKY"}),
        ("ws-gpu-04", lambda body: {**body, "occurredAt": "2026-10-15T12:00:00"}),
        ("ws-gpu-04", lambda body: {**body, "schemaVersion": "2.0"}),
        ("ws-gpu-04", lambda body: {**body, "gpuSamples": []}),
    ],
    ids=[
        "malformed-node-id",
        "missing-field",
        "client-supplied-state",
        "bad-enum",
        "naive-timestamp",
        "schema-version",
        "no-samples",
    ],
)
def test_malformed_requests_are_422_schema_errors_with_zero_effects(client, container, node_id, mutate) -> None:
    before = effect_probe(container.engine)
    assert_rejected(post(client, node_id, mutate(heartbeat_body("ws-gpu-04", T0))), 422, "ERR_SCHEMA")
    assert effect_probe(container.engine) == before


def test_foreign_gpu_identifier_mutates_neither_node(client: TestClient, container: Container) -> None:
    before = effect_probe(container.engine)
    body = heartbeat_body("ws-gpu-09", T0)
    body["gpuSamples"][0]["gpuDeviceId"] = "ws-gpu-10-gpu-0"

    response = post(client, "ws-gpu-09", body)

    assert_rejected(response, 422, "ERR_SCHEMA")
    assert response.json()["details"]["expected"] == ["ws-gpu-09-gpu-0"]
    assert effect_probe(container.engine) == before


@pytest.mark.parametrize(
    "overrides",
    [{"vram_gb": (24.001,)}, {"storageFreeGb": 500.5}],
    ids=["vram-over-24gb", "storage-over-500gb"],
)
def test_values_over_capacity_are_422_capacity_errors(client, container, overrides) -> None:
    before = effect_probe(container.engine)
    assert_rejected(post(client, "ws-gpu-04", heartbeat_body("ws-gpu-04", T0, **overrides)), 422, "ERR_CAPACITY_RANGE")
    assert effect_probe(container.engine) == before


def test_receive_time_later_than_server_clock_is_rejected(client: TestClient, container: Container) -> None:
    before = effect_probe(container.engine)
    body = heartbeat_body("ws-gpu-04", T0, receivedAt=(T0 + timedelta(seconds=1)).isoformat())
    assert_rejected(post(client, "ws-gpu-04", body), 422, "ERR_SCHEMA")
    assert effect_probe(container.engine) == before


@pytest.mark.parametrize(
    ("driver", "rule"),
    [("UNKNOWN", "ERR_DRIVER_HEALTH_UNKNOWN"), ("UNHEALTHY", "ERR_DRIVER_UNHEALTHY")],
)
def test_degraded_driver_cordons_and_opens_one_alert(client: TestClient, container: Container, driver, rule) -> None:
    body = post(client, "ws-gpu-06", heartbeat_body("ws-gpu-06", T0, driver=driver)).json()

    assert (body["state"], body["cordoned"]) == ("DEGRADED", True)
    assert body["explanation"]["ruleIds"] == [rule]
    assert body["explanation"]["thresholds"] == {"driverHealth": {"operator": "==", "value": "HEALTHY"}}
    with container.engine.connect() as connection:
        alerts = connection.execute(select(AlertRow).where(AlertRow.node_id == "ws-gpu-06")).all()
    assert [(a.reason_code, a.update_count, a.closed_at) for a in alerts] == [(rule, 1, None)]


def test_retained_reason_holds_degraded_and_cites_its_original_evidence(
    client: TestClient, container: Container, fake_clock
) -> None:
    first = post(client, "ws-gpu-06", heartbeat_body("ws-gpu-06", T0, driver="UNKNOWN")).json()
    later = fake_clock.advance(seconds=10)

    second = post(client, "ws-gpu-06", heartbeat_body("ws-gpu-06", later, seq=2, driver="HEALTHY")).json()

    assert (second["state"], second["cordoned"]) == ("DEGRADED", True), "no approved clear rule: reason retained"
    explanation = second["explanation"]
    assert explanation["ruleIds"] == ["ERR_DRIVER_HEALTH_UNKNOWN", "ERR_POLICY_UNRESOLVED"]
    assert explanation["evidenceIds"] == [second["eventId"], first["eventId"]]
    assert explanation["observedValues"]["retainedReasonEvidence"] == {"ERR_DRIVER_HEALTH_UNKNOWN": [first["eventId"]]}
    with container.engine.connect() as connection:
        alert = connection.execute(select(AlertRow).where(AlertRow.node_id == "ws-gpu-06")).one()
    assert (alert.update_count, alert.last_observed_at) == (1, T0), "a heartbeat that did not observe the fault"


def test_exact_replay_returns_recorded_result_without_new_effects(client: TestClient, container: Container) -> None:
    body = heartbeat_body("ws-gpu-03", T0)
    first = post(client, "ws-gpu-03", body).json()
    after_first = effect_probe(container.engine)

    replay = post(client, "ws-gpu-03", body)

    assert replay.status_code == 200
    assert replay.json() == {**first, "outcome": "DUPLICATE"}
    assert effect_probe(container.engine) == after_first


def test_event_id_reuse_with_different_payload_is_409(client: TestClient, container: Container) -> None:
    body = heartbeat_body("ws-gpu-03", T0)
    post(client, "ws-gpu-03", body)
    after_first = effect_probe(container.engine)

    assert_rejected(post(client, "ws-gpu-03", {**body, "storageFreeGb": 100.0}), 409, "ERR_IDEMPOTENCY_CONFLICT")
    assert effect_probe(container.engine) == after_first


def test_reused_source_sequence_with_new_event_is_ambiguous_409(client: TestClient, container: Container) -> None:
    post(client, "ws-gpu-03", heartbeat_body("ws-gpu-03", T0, seq=7))
    after_first = effect_probe(container.engine)

    other = heartbeat_body("ws-gpu-03", T0, seq=7, temperatures=(50.0,))
    assert_rejected(post(client, "ws-gpu-03", other), 409, "ERR_ORDER_AMBIGUOUS")
    assert effect_probe(container.engine) == after_first


def test_unproven_boot_change_is_rejected_without_effects(client, container, fake_clock) -> None:
    post(client, "ws-gpu-05", heartbeat_body("ws-gpu-05", T0))
    after_first = effect_probe(container.engine)
    later = fake_clock.advance(seconds=10)

    assert_rejected(
        post(client, "ws-gpu-05", heartbeat_body("ws-gpu-05", later, seq=2, boot="boot-b")),
        409,
        "ERR_BOOT_SUCCESSION",
    )
    assert effect_probe(container.engine) == after_first


@pytest.mark.parametrize(
    "successor_evidence",
    [{"previousBootSessionId": "boot-a"}, {"stateLoss": True}],
    ids=["linked-successor", "explicit-state-loss"],
)
def test_proven_boot_change_is_detected_and_enters_recovery(client, container, fake_clock, successor_evidence) -> None:
    post(client, "ws-gpu-05", heartbeat_body("ws-gpu-05", T0))
    later = fake_clock.advance(seconds=10)

    response = post(
        client,
        "ws-gpu-05",
        heartbeat_body("ws-gpu-05", later, seq=1, boot="boot-b", **successor_evidence),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "BOOT_CHANGE_DETECTED"
    assert (body["state"], body["cordoned"], body["nodeRevision"]) == ("RECOVERING", True, 2)
    assert body["explanation"]["observedValues"]["priorBootSessionId"] == "boot-a"
    assert body["explanation"]["observedValues"]["evidenceEpoch"] == 1
    row = node_row(container, "ws-gpu-05")
    assert (row.current_boot_session_id, row.evidence_epoch) == ("boot-b", 1)
    with container.engine.connect() as connection:
        telemetry = connection.execute(
            select(TelemetrySnapshotRow).where(TelemetrySnapshotRow.event_id == UUID(body["eventId"]))
        ).one()
        audit = connection.execute(select(AuditEventRow).where(AuditEventRow.event_id == UUID(body["eventId"]))).one()
    assert (telemetry.disposition, telemetry.evidence_epoch, telemetry.is_current) == (
        "BOOT_CHANGE_DETECTED",
        1,
        True,
    )
    assert audit.event_type == "RebootDetected"


def test_older_heartbeat_is_persisted_late_without_stale_overwrite(client, container, fake_clock) -> None:
    post(client, "ws-gpu-03", heartbeat_body("ws-gpu-03", T0, seq=10))
    current_at = fake_clock.advance(seconds=10)
    current = post(client, "ws-gpu-03", heartbeat_body("ws-gpu-03", current_at, seq=11)).json()
    before_late = effect_probe(container.engine)
    fake_clock.advance(seconds=10)

    late = post(
        client,
        "ws-gpu-03",
        heartbeat_body("ws-gpu-03", T0 + timedelta(seconds=5), seq=9, temperatures=(75.0,)),
    )

    assert late.status_code == 200, late.text
    body = late.json()
    assert body["outcome"] == "LATE_IGNORED"
    assert (body["nodeRevision"], body["state"], body["cordoned"]) == (2, "HEALTHY", False)
    assert body["explanation"]["ruleIds"] == ["ERR_LATE_EVENT"]
    assert body["explanation"]["observedValues"]["currentSourceSequence"] == 11
    row = node_row(container, "ws-gpu-03")
    assert (row.revision, row.last_accepted_event_at) == (2, current_at)
    with container.engine.connect() as connection:
        snapshots = connection.execute(
            select(TelemetrySnapshotRow)
            .where(TelemetrySnapshotRow.node_id == "ws-gpu-03")
            .order_by(TelemetrySnapshotRow.ingest_offset)
        ).all()
        histories = connection.scalar(
            select(func.count()).select_from(NodeStateHistoryRow).where(NodeStateHistoryRow.node_id == "ws-gpu-03")
        )
    assert [(row.disposition, row.is_current) for row in snapshots] == [
        ("APPLIED", False),
        ("APPLIED", True),
        ("LATE_IGNORED", False),
    ]
    assert str(snapshots[1].event_id) == current["eventId"]
    assert histories == 1
    after_late = effect_probe(container.engine)
    assert after_late[0] == before_late[0]
    assert after_late[1] == (
        before_late[1][0] + 1,
        before_late[1][1] + 1,
        before_late[1][2],
        before_late[1][3],
        before_late[1][4] + 1,
    )

    replay = post(
        client,
        "ws-gpu-03",
        heartbeat_body("ws-gpu-03", T0 + timedelta(seconds=5), seq=9, temperatures=(75.0,)),
    )
    assert replay.json() == {**body, "outcome": "DUPLICATE"}
    assert effect_probe(container.engine) == after_late


def test_non_increasing_sequence_with_newer_time_is_late_ignored(client, container, fake_clock) -> None:
    post(client, "ws-gpu-03", heartbeat_body("ws-gpu-03", T0, seq=10))
    before_late = effect_probe(container.engine)
    later = fake_clock.advance(seconds=10)

    response = post(client, "ws-gpu-03", heartbeat_body("ws-gpu-03", later, seq=10))

    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "LATE_IGNORED"
    row = node_row(container, "ws-gpu-03")
    assert (row.revision, row.last_accepted_event_at) == (1, T0)
    after_late = effect_probe(container.engine)
    assert after_late[0] == before_late[0]
    assert after_late[1] == (
        before_late[1][0] + 1,
        before_late[1][1] + 1,
        before_late[1][2],
        before_late[1][3],
        before_late[1][4] + 1,
    )


def test_receive_clock_moving_backwards_is_rejected(client, container, fake_clock, monkeypatch) -> None:
    post(client, "ws-gpu-12", heartbeat_body("ws-gpu-12", T0))
    after_first = effect_probe(container.engine)
    earlier = T0 - timedelta(seconds=1)
    monkeypatch.setattr(fake_clock, "now", lambda: earlier)

    assert_rejected(post(client, "ws-gpu-12", heartbeat_body("ws-gpu-12", earlier, seq=2)), 409, "ERR_CLOCK_ORDER")
    assert effect_probe(container.engine) == after_first


def test_replay_with_equivalent_offset_and_sample_order_is_a_duplicate(
    client: TestClient, container: Container
) -> None:
    body = heartbeat_body("central-gpu-server", T0, temperatures=(50.0, 51.0), vram_gb=(1.0, 2.0))
    first = post(client, "central-gpu-server", body).json()
    after_first = effect_probe(container.engine)
    equivalent = {
        **body,
        "occurredAt": "2026-10-15T14:00:00+02:00",
        "receivedAt": "2026-10-15T12:00:00Z",
        "gpuSamples": list(reversed(body["gpuSamples"])),
    }

    replay = post(client, "central-gpu-server", equivalent)

    assert replay.status_code == 200, replay.text
    assert replay.json() == {**first, "outcome": "DUPLICATE"}
    assert effect_probe(container.engine) == after_first


def test_event_id_reused_on_another_node_is_409_naming_the_original_node(client: TestClient, container) -> None:
    body = heartbeat_body("ws-gpu-03", T0)
    post(client, "ws-gpu-03", body)
    after_first = effect_probe(container.engine)
    other_node = heartbeat_body("ws-gpu-13", T0, eventId=body["eventId"])

    response = post(client, "ws-gpu-13", other_node)

    assert_rejected(response, 409, "ERR_IDEMPOTENCY_CONFLICT")
    assert response.json()["details"]["recordedNodeId"] == "ws-gpu-03"
    assert effect_probe(container.engine) == after_first


def test_nan_temperature_is_rejected_at_the_boundary(client: TestClient, container: Container) -> None:
    before = effect_probe(container.engine)
    raw = json.dumps(heartbeat_body("ws-gpu-04", T0, temperatures=(float("nan"),)))

    response = client.post("/v1/nodes/ws-gpu-04/heartbeats", content=raw, headers={"Content-Type": "application/json"})

    assert_rejected(response, 422, "ERR_SCHEMA")
    assert effect_probe(container.engine) == before
