from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gpu_lab_twin.domain.heartbeat import GpuSample, HeartbeatPayload
from gpu_lab_twin.domain.heartbeat_policy import THERMAL_THRESHOLD_C, reasons_from
from gpu_lab_twin.domain.node_state import DriverHealth, NodeFacts, NodeState, ReasonCode, evaluate

AT = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def server_payload(t0: float, t1: float) -> HeartbeatPayload:
    return HeartbeatPayload(
        event_id=uuid4(),
        occurred_at=AT,
        received_at=AT,
        schema_version="1.0",
        boot_session_id="boot-a",
        previous_boot_session_id=None,
        state_loss=False,
        source_sequence=1,
        gpu_samples=(GpuSample("central-gpu-server-gpu-0", t0, 1.0), GpuSample("central-gpu-server-gpu-1", t1, 1.0)),
        driver_health=DriverHealth.HEALTHY,
        storage_free_gb=100.0,
    )


@pytest.mark.parametrize(
    ("temperature", "thermal"),
    [(88.0, False), (88.0001, True), (88.1, True), (91.0, True), (87.9, False)],
)
def test_threshold_is_strictly_greater_than_88(temperature: float, thermal: bool) -> None:
    assert (ReasonCode.THERMAL in reasons_from(server_payload(temperature, 40.0))) is thermal


@given(t0=st.floats(min_value=0, max_value=150), t1=st.floats(min_value=0, max_value=150))
def test_any_single_hot_gpu_marks_the_whole_node(t0: float, t1: float) -> None:
    thermal = ReasonCode.THERMAL in reasons_from(server_payload(t0, t1))
    assert thermal is (max(t0, t1) > THERMAL_THRESHOLD_C)


def test_hottest_sample_ties_resolve_by_device_id() -> None:
    payload = server_payload(91.0, 91.0)
    reversed_payload = replace(payload, gpu_samples=tuple(reversed(payload.gpu_samples)))
    assert (
        payload.hottest_sample.gpu_device_id
        == reversed_payload.hottest_sample.gpu_device_id
        == ("central-gpu-server-gpu-0")
    )


def test_thermal_reason_degrades_and_cordons_under_higher_precedence_states() -> None:
    thermal = frozenset({ReasonCode.THERMAL})
    assert evaluate(NodeFacts(has_current_heartbeat=True, reasons=thermal)).state is NodeState.DEGRADED
    offline = evaluate(NodeFacts(has_current_heartbeat=False, reasons=thermal | {ReasonCode.SILENT}))
    recovering = evaluate(NodeFacts(has_current_heartbeat=True, reasons=thermal | {ReasonCode.RECOVERY_PENDING}))
    assert (offline.state, offline.cordoned, ReasonCode.THERMAL in offline.reason_codes) == (
        NodeState.OFFLINE,
        True,
        True,
    )
    assert (recovering.state, recovering.cordoned) == (NodeState.RECOVERING, True)
