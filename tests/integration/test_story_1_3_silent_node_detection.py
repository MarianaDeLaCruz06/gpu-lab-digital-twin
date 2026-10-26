"""Story 1.3 (task annex 3.2): silent node detection and the OFFLINE transition."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from gpu_lab_twin.adapters.db.models import AlertRow, AuditEventRow, NodeRow, NodeStateHistoryRow
from gpu_lab_twin.adapters.sim.fake_clock import FakeClock
from gpu_lab_twin.bootstrap import Container
from gpu_lab_twin.domain.errors import DomainError, ErrorCode
from tests.conftest import T0
from tests.support import effect_probe, heartbeat_body


def beat(client: TestClient, node_id: str, at: datetime, seq: int = 1, **overrides) -> dict:
    response = client.post(f"/v1/nodes/{node_id}/heartbeats", json=heartbeat_body(node_id, at, seq=seq, **overrides))
    assert response.status_code == 200, response.text
    return response.json()


def node(container: Container, node_id: str):
    with container.engine.connect() as connection:
        return connection.execute(select(NodeRow).where(NodeRow.node_id == node_id)).one()


def alerts(container: Container, node_id: str) -> list[tuple[str, bool]]:
    with container.engine.connect() as connection:
        rows = connection.execute(select(AlertRow).where(AlertRow.node_id == node_id).order_by(AlertRow.opened_at))
        return [(row.reason_code, row.closed_at is None) for row in rows]


# Annex scenario: Given "ws-gpu-12" has last heartbeat 45 s ago (interval 10 s, threshold 30 s), When the liveness
# evaluation routine runs, Then it is OFFLINE and an alert event NODE_SILENT_TIMEOUT (contract: ERR_SILENT) is emitted.
def test_silent_node_goes_offline_cordoned_with_alert_and_explanation(
    client: TestClient, container: Container, fake_clock: FakeClock
) -> None:
    heartbeat = beat(client, "ws-gpu-12", T0)
    fake_clock.advance(seconds=45)

    report = container.liveness.evaluate_fleet_liveness()

    assert report.transitioned_node_ids == ("ws-gpu-12",), "nodes that never reported stay UNKNOWN"
    row = node(container, "ws-gpu-12")
    assert (row.state, row.cordoned, row.connectivity) == ("OFFLINE", True, "SILENT")
    assert row.active_reason_codes == ["ERR_SILENT"]
    assert row.last_accepted_receive_at == T0, "silence never rewrites the last accepted receive time"
    assert alerts(container, "ws-gpu-12") == [("ERR_SILENT", True)]

    with container.engine.connect() as connection:
        history = connection.execute(
            select(NodeStateHistoryRow)
            .where(NodeStateHistoryRow.node_id == "ws-gpu-12")
            .order_by(NodeStateHistoryRow.node_revision)
        ).all()
        audit = connection.execute(select(AuditEventRow).where(AuditEventRow.event_type == "NodeSilenceDetected")).one()
    silence = history[-1]
    assert (silence.prior_state, silence.result_state, silence.result_cordoned) == ("HEALTHY", "OFFLINE", True)
    explanation = silence.explanation
    assert explanation["ruleIds"] == ["ERR_SILENT"]
    assert explanation["observedValues"]["missedIntervals"] == 4.5
    assert explanation["observedValues"]["elapsedSeconds"] == 45.0
    assert explanation["observedValues"]["heartbeatIntervalMs"] == 10_000
    assert explanation["thresholds"] == {"missedIntervals": {"operator": ">", "value": 3}}
    assert heartbeat["eventId"] in explanation["evidenceIds"]
    assert audit.node_id == "ws-gpu-12"
    assert audit.body["annexEventName"] == "NODE_SILENT_TIMEOUT"


def test_exactly_three_intervals_is_not_silent(client: TestClient, container: Container, fake_clock) -> None:
    beat(client, "ws-gpu-12", T0)
    before = effect_probe(container.engine)
    fake_clock.advance(seconds=30)

    report = container.liveness.evaluate_fleet_liveness()

    assert report.transitioned_node_ids == ()
    assert node(container, "ws-gpu-12").state == "HEALTHY"
    assert effect_probe(container.engine) == before


def test_just_past_three_intervals_is_silent(client: TestClient, container: Container, fake_clock) -> None:
    beat(client, "ws-gpu-12", T0)
    fake_clock.advance(seconds=30.001)

    assert container.liveness.evaluate_fleet_liveness().transitioned_node_ids == ("ws-gpu-12",)
    assert node(container, "ws-gpu-12").state == "OFFLINE"


def test_node_that_never_reported_stays_unknown(client: TestClient, container: Container, fake_clock) -> None:
    fake_clock.advance(seconds=3600)

    report = container.liveness.evaluate_fleet_liveness()

    assert report.transitioned_node_ids == ()
    assert (node(container, "central-gpu-server").state, node(container, "central-gpu-server").cordoned) == (
        "UNKNOWN",
        True,
    )


def test_already_offline_node_is_held_without_new_rows(client: TestClient, container: Container, fake_clock) -> None:
    beat(client, "ws-gpu-12", T0)
    fake_clock.advance(seconds=45)
    container.liveness.evaluate_fleet_liveness()
    after_offline = effect_probe(container.engine)
    fake_clock.advance(seconds=60)

    report = container.liveness.evaluate_fleet_liveness()

    assert (report.transitioned_node_ids, report.held_node_ids) == ((), ("ws-gpu-12",))
    assert effect_probe(container.engine) == after_offline


def test_degraded_node_goes_offline_and_keeps_its_degradation_reason(client, container, fake_clock) -> None:
    beat(client, "ws-gpu-06", T0, driver="UNKNOWN")
    fake_clock.advance(seconds=31)

    container.liveness.evaluate_fleet_liveness()

    row = node(container, "ws-gpu-06")
    assert (row.state, row.cordoned) == ("OFFLINE", True)
    assert set(row.active_reason_codes) == {"ERR_SILENT", "ERR_DRIVER_HEALTH_UNKNOWN"}


@pytest.mark.parametrize("step_seconds", [0, -1], ids=["same-instant", "backwards"])
def test_evaluation_clock_must_strictly_advance(client, container: Container, fake_clock, step_seconds: float) -> None:
    first = fake_clock.advance(seconds=10)
    container.liveness.evaluate_fleet_liveness()
    before = effect_probe(container.engine)

    with pytest.raises(DomainError) as caught:
        container.liveness.evaluate_fleet_liveness(first + timedelta(seconds=step_seconds))

    assert caught.value.code is ErrorCode.ERR_CLOCK_ORDER
    assert effect_probe(container.engine) == before


def test_fleet_scan_transitions_exactly_the_silent_nodes(client: TestClient, container: Container, fake_clock) -> None:
    for node_id in ("ws-gpu-01", "ws-gpu-02", "ws-gpu-03", "ws-gpu-04", "central-gpu-server"):
        if node_id == "central-gpu-server":
            beat(client, node_id, T0, temperatures=(40.0, 41.0), vram_gb=(0.0, 0.0))
        else:
            beat(client, node_id, T0)
    fresh = fake_clock.advance(seconds=20)
    beat(client, "ws-gpu-02", fresh, seq=2)
    beat(client, "ws-gpu-04", fresh, seq=2)
    fake_clock.advance(seconds=15)

    report = container.liveness.evaluate_fleet_liveness()

    assert report.transitioned_node_ids == ("ws-gpu-01", "ws-gpu-03", "central-gpu-server")
    assert [node(container, n).state for n in ("ws-gpu-02", "ws-gpu-04")] == ["HEALTHY", "HEALTHY"]
    beaten = ["ws-gpu-01", "ws-gpu-02", "ws-gpu-03", "ws-gpu-04", "central-gpu-server"]
    with container.engine.connect() as connection:
        untouched = connection.execute(
            select(NodeRow.state, NodeRow.revision).where(NodeRow.node_id.not_in(beaten))
        ).all()
    assert len(untouched) == 27 and set(untouched) == {("UNKNOWN", 0)}


def test_heartbeat_after_offline_enters_recovering_not_healthy(
    client: TestClient, container: Container, fake_clock
) -> None:
    beat(client, "ws-gpu-12", T0)
    fake_clock.advance(seconds=45)
    container.liveness.evaluate_fleet_liveness()
    back = fake_clock.advance(seconds=1)

    returned = beat(client, "ws-gpu-12", back, seq=2)

    assert (returned["state"], returned["cordoned"], returned["connectivityStatus"]) == ("RECOVERING", True, "ONLINE")
    assert returned["explanation"]["ruleIds"] == ["RECOVERY_PENDING"]
    assert returned["explanation"]["thresholds"] == {"recoveryPolicy": {"policyId": "ODD-3", "status": "unresolved"}}
    assert alerts(container, "ws-gpu-12") == [("ERR_SILENT", False), ("RECOVERY_PENDING", True)]

    later = fake_clock.advance(seconds=10)
    held = beat(client, "ws-gpu-12", later, seq=3)
    assert (held["state"], held["cordoned"]) == ("RECOVERING", True), "no recovery exit until ODD-3 is defined"
    assert "ERR_POLICY_UNRESOLVED" in held["explanation"]["ruleIds"]


def test_fleet_view_shows_offline_node_with_last_known_readings(client: TestClient, container, fake_clock) -> None:
    beat(client, "ws-gpu-12", T0, temperatures=(65.0,), vram_gb=(12.0,))
    fake_clock.advance(seconds=45)
    container.liveness.evaluate_fleet_liveness()

    summary = next(n for n in client.get("/v1/nodes").json()["nodes"] if n["nodeId"] == "ws-gpu-12")

    assert (summary["state"], summary["cordoned"], summary["connectivityStatus"]) == ("OFFLINE", True, "SILENT")
    assert datetime.fromisoformat(summary["lastHeartbeatReceivedAt"]) == T0
    assert summary["gpus"][0]["temperatureC"] == 65.0
    assert summary["gpus"][0]["vramOccupiedGb"] == 12.0


def history(container: Container, node_id: str) -> list:
    with container.engine.connect() as connection:
        return connection.execute(
            select(NodeStateHistoryRow)
            .where(NodeStateHistoryRow.node_id == node_id)
            .order_by(NodeStateHistoryRow.node_revision)
        ).all()


def open_alerts(container: Container, node_id: str) -> set[str]:
    return {reason for reason, is_open in alerts(container, node_id) if is_open}


def test_return_after_offline_is_recorded_in_history(client: TestClient, container: Container, fake_clock) -> None:
    beat(client, "ws-gpu-12", T0)
    fake_clock.advance(seconds=45)
    container.liveness.evaluate_fleet_liveness()
    returned = beat(client, "ws-gpu-12", fake_clock.advance(seconds=1), seq=2)

    last = history(container, "ws-gpu-12")[-1]
    assert (last.prior_state, last.result_state, last.result_cordoned) == ("OFFLINE", "RECOVERING", True)
    assert str(last.source_event_id) == returned["eventId"]


def test_recovering_node_that_goes_silent_again_returns_to_recovering(client, container, fake_clock) -> None:
    beat(client, "ws-gpu-12", T0)
    fake_clock.advance(seconds=45)
    container.liveness.evaluate_fleet_liveness()
    beat(client, "ws-gpu-12", fake_clock.advance(seconds=1), seq=2)
    fake_clock.advance(seconds=31)

    container.liveness.evaluate_fleet_liveness()

    row = node(container, "ws-gpu-12")
    assert (row.state, row.cordoned) == ("OFFLINE", True)
    assert set(row.active_reason_codes) == {"ERR_SILENT", "RECOVERY_PENDING"}
    assert open_alerts(container, "ws-gpu-12") == {"ERR_SILENT", "RECOVERY_PENDING"}

    again = beat(client, "ws-gpu-12", fake_clock.advance(seconds=1), seq=3)
    assert (again["state"], again["cordoned"]) == ("RECOVERING", True)
    assert open_alerts(container, "ws-gpu-12") == {"RECOVERY_PENDING"}


def test_silence_explanation_cites_reasons_that_stay_active(client, container, fake_clock) -> None:
    degraded = beat(client, "ws-gpu-06", T0, driver="UNKNOWN")
    fake_clock.advance(seconds=31)

    container.liveness.evaluate_fleet_liveness()

    explanation = history(container, "ws-gpu-06")[-1].explanation
    assert explanation["ruleIds"] == ["ERR_SILENT"]
    retained = explanation["observedValues"]["retainedReasonEvidence"]
    assert retained == {"ERR_DRIVER_HEALTH_UNKNOWN": [degraded["eventId"]]}
    assert degraded["eventId"] in explanation["evidenceIds"]
    assert "ERR_DRIVER_HEALTH_UNKNOWN" in explanation["summary"]


def test_one_failed_commit_does_not_stop_the_fleet_scan(client, container, fake_clock, monkeypatch) -> None:
    for node_id in ("ws-gpu-01", "ws-gpu-02", "ws-gpu-03"):
        beat(client, node_id, T0)
    fake_clock.advance(seconds=31)
    real_commit = container.nodes.commit_transition

    def failing_for_ws_gpu_02(commit):
        if commit.projection.node_id == "ws-gpu-02":
            raise DomainError(ErrorCode.ERR_INGRESS_UNAVAILABLE, "storage rejected the write")
        return real_commit(commit)

    monkeypatch.setattr(container.nodes, "commit_transition", failing_for_ws_gpu_02)

    report = container.liveness.evaluate_fleet_liveness()

    assert (report.transitioned_node_ids, report.failed_node_ids) == (("ws-gpu-01", "ws-gpu-03"), ("ws-gpu-02",))
    states = [node(container, n).state for n in ("ws-gpu-01", "ws-gpu-02", "ws-gpu-03")]
    assert states == ["OFFLINE", "HEALTHY", "OFFLINE"]

    monkeypatch.setattr(container.nodes, "commit_transition", real_commit)
    fake_clock.advance(seconds=5)
    assert container.liveness.evaluate_fleet_liveness().transitioned_node_ids == ("ws-gpu-02",)


@pytest.mark.parametrize(
    ("make_instant", "code"),
    [
        (lambda clock: clock.now() + timedelta(seconds=1), ErrorCode.ERR_CLOCK_ORDER),
        (lambda clock: clock.now().replace(tzinfo=None), ErrorCode.ERR_SCHEMA),
    ],
    ids=["future-instant", "naive-instant"],
)
def test_invalid_explicit_evaluation_instant_is_rejected(client, container, fake_clock, make_instant, code) -> None:
    beat(client, "ws-gpu-12", T0)
    fake_clock.advance(seconds=45)
    before = effect_probe(container.engine)

    with pytest.raises(DomainError) as caught:
        container.liveness.evaluate_fleet_liveness(make_instant(fake_clock))

    assert caught.value.code is code
    assert effect_probe(container.engine) == before


def test_configured_interval_is_authoritative_over_the_stored_copy(client, container, fake_clock) -> None:
    beat(client, "ws-gpu-12", T0)
    with container.engine.begin() as connection:
        connection.execute(
            NodeRow.__table__.update().where(NodeRow.node_id == "ws-gpu-12").values(heartbeat_interval_ms=3_600_000)
        )
    fake_clock.advance(seconds=31)

    assert container.liveness.evaluate_fleet_liveness().transitioned_node_ids == ("ws-gpu-12",)
