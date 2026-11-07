"""Story 3.4 Flow A: canonical AD-5 containment of five-second connectivity pulses."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from gpu_lab_twin.adapters.db.models import AlertRow, AuditEventRow, NodeRow
from gpu_lab_twin.adapters.sim.fake_clock import FakeClock
from gpu_lab_twin.bootstrap import Container
from gpu_lab_twin.domain.errors import DomainError, ErrorCode
from tests.conftest import T0
from tests.support import heartbeat_body

NODE_ID = "ws-gpu-14"
UNRESOLVED = ErrorCode.ERR_POLICY_UNRESOLVED.value
FLAPPING = "ERR_CONNECTIVITY_FLAPPING"


def _healthy(client: TestClient) -> None:
    response = client.post(f"/v1/nodes/{NODE_ID}/heartbeats", json=heartbeat_body(NODE_ID, T0))
    assert response.status_code == 200, response.text


def _port(container: Container):
    port = getattr(container, "connectivity", None)
    assert port is not None, "AC requires a connectivity observation inbound port"
    return port


def _event_id(index: int) -> UUID:
    return uuid5(NAMESPACE_URL, f"story-3.4:{NODE_ID}:{index}")


def _observe(container: Container, fake_clock: FakeClock, index: int, status: str):
    fake_clock.advance(seconds=5)
    return _port(container).observe(
        NODE_ID,
        event_id=_event_id(index),
        status=status,
        observed_at=fake_clock.now(),
    )


def _node_tuple(container: Container) -> tuple:
    with container.engine.connect() as connection:
        row = connection.execute(select(NodeRow).where(NodeRow.node_id == NODE_ID)).one()
    return row.state, row.connectivity, row.cordoned, row.revision


@pytest.mark.parametrize("pulse_count", [12])
def test_ac1_five_second_pulses_preserve_stable_public_tuple_and_eligibility(
    client: TestClient, container: Container, fake_clock: FakeClock, pulse_count: int
) -> None:
    _healthy(client)
    stable = _node_tuple(container)

    for index in range(1, pulse_count + 1):
        status = "OFFLINE" if index % 2 else "ONLINE"
        result = _observe(container, fake_clock, index, status)
        assert result.outcome == "HELD_POLICY_UNRESOLVED"
        assert _node_tuple(container) == stable

    assert stable == ("HEALTHY", "ONLINE", False, 1)


def test_ac2_exact_threshold_and_just_beyond_do_not_invent_odd5_policy(
    client: TestClient, container: Container, fake_clock: FakeClock
) -> None:
    _healthy(client)

    results = [_observe(container, fake_clock, index, "OFFLINE" if index % 2 else "ONLINE") for index in range(1, 5)]

    assert results[2].reason_code == UNRESOLVED
    assert results[3].reason_code == UNRESOLVED
    assert all(result.policy_id == "ODD-5" for result in results)
    assert all(result.state == "HEALTHY" and result.cordoned is False for result in results)


def test_ac3_unique_pulses_create_one_diagnostic_zero_flapping_alerts_and_one_audit_each(
    client: TestClient, container: Container, fake_clock: FakeClock
) -> None:
    _healthy(client)
    pulse_count = 12
    for index in range(1, pulse_count + 1):
        _observe(container, fake_clock, index, "OFFLINE" if index % 2 else "ONLINE")

    with container.engine.connect() as connection:
        unresolved = connection.scalar(
            select(func.count())
            .select_from(AlertRow)
            .where(
                AlertRow.node_id == NODE_ID,
                AlertRow.reason_code == UNRESOLVED,
                AlertRow.closed_at.is_(None),
            )
        )
        flapping = connection.scalar(
            select(func.count())
            .select_from(AlertRow)
            .where(
                AlertRow.node_id == NODE_ID,
                AlertRow.reason_code == FLAPPING,
                AlertRow.closed_at.is_(None),
            )
        )
        evidence = connection.scalar(
            select(func.count())
            .select_from(AuditEventRow)
            .where(
                AuditEventRow.node_id == NODE_ID,
                AuditEventRow.event_type == "ConnectivityObserved",
            )
        )

    assert unresolved == 1
    assert flapping == 0
    assert evidence == pulse_count


def test_ac4_duplicate_is_idempotent_and_conflicting_reuse_is_rejected_atomically(
    client: TestClient, container: Container, fake_clock: FakeClock
) -> None:
    _healthy(client)
    event_id = _event_id(1)
    at = fake_clock.advance(seconds=5)
    port = _port(container)
    first = port.observe(NODE_ID, event_id=event_id, status="OFFLINE", observed_at=at)
    replay = port.observe(NODE_ID, event_id=event_id, status="OFFLINE", observed_at=at)

    assert replay.outcome == "DUPLICATE"
    assert replay.as_document() == {**first.as_document(), "outcome": "DUPLICATE"}
    with container.engine.connect() as connection:
        before = (
            connection.scalar(select(func.count()).select_from(AuditEventRow)),
            connection.scalar(select(func.sum(AlertRow.update_count)).where(AlertRow.node_id == NODE_ID)),
        )

    with pytest.raises(DomainError) as caught:
        port.observe(NODE_ID, event_id=event_id, status="ONLINE", observed_at=at)
    assert caught.value.code is ErrorCode.ERR_IDEMPOTENCY_CONFLICT

    with container.engine.connect() as connection:
        after = (
            connection.scalar(select(func.count()).select_from(AuditEventRow)),
            connection.scalar(select(func.sum(AlertRow.update_count)).where(AlertRow.node_id == NODE_ID)),
        )
    assert after == before


def test_concurrent_duplicate_observations_commit_once(
    client: TestClient, container: Container, fake_clock: FakeClock
) -> None:
    _healthy(client)
    event_id = _event_id(99)
    observed_at = fake_clock.advance(seconds=5)
    port = _port(container)

    def submit() -> str:
        return port.observe(NODE_ID, event_id=event_id, status="OFFLINE", observed_at=observed_at).outcome

    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(lambda _: submit(), range(8)))

    assert outcomes.count("HELD_POLICY_UNRESOLVED") == 1
    assert outcomes.count("DUPLICATE") == 7
    with container.engine.connect() as connection:
        evidence = connection.scalar(
            select(func.count()).select_from(AuditEventRow).where(AuditEventRow.event_id == event_id)
        )
        update_count = connection.scalar(
            select(AlertRow.update_count).where(
                AlertRow.node_id == NODE_ID,
                AlertRow.reason_code == UNRESOLVED,
                AlertRow.closed_at.is_(None),
            )
        )
    assert (evidence, update_count) == (1, 1)


def test_invalid_or_out_of_order_observation_time_has_zero_effects(
    client: TestClient, container: Container, fake_clock: FakeClock
) -> None:
    _healthy(client)
    port = _port(container)

    with pytest.raises(DomainError) as naive:
        port.observe(NODE_ID, event_id=_event_id(201), status="OFFLINE", observed_at=datetime(2026, 11, 7))
    assert naive.value.code is ErrorCode.ERR_SCHEMA

    with pytest.raises(DomainError) as future:
        port.observe(
            NODE_ID,
            event_id=_event_id(202),
            status="OFFLINE",
            observed_at=fake_clock.now() + timedelta(microseconds=1),
        )
    assert future.value.code is ErrorCode.ERR_CLOCK_ORDER

    accepted_at = fake_clock.advance(seconds=5)
    port.observe(NODE_ID, event_id=_event_id(203), status="OFFLINE", observed_at=accepted_at)
    with container.engine.connect() as connection:
        before = (
            connection.scalar(select(func.count()).select_from(AuditEventRow)),
            connection.scalar(select(func.sum(AlertRow.update_count)).where(AlertRow.node_id == NODE_ID)),
        )

    with pytest.raises(DomainError) as stale:
        port.observe(NODE_ID, event_id=_event_id(204), status="ONLINE", observed_at=T0)
    assert stale.value.code is ErrorCode.ERR_CLOCK_ORDER

    with container.engine.connect() as connection:
        after = (
            connection.scalar(select(func.count()).select_from(AuditEventRow)),
            connection.scalar(select(func.sum(AlertRow.update_count)).where(AlertRow.node_id == NODE_ID)),
        )
    assert after == before
