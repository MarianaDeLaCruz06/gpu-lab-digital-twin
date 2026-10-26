from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from gpu_lab_twin.domain.errors import DomainError, ErrorCode
from gpu_lab_twin.domain.fleet import GpuDeviceSpec, NodeKind, NodeSpec
from gpu_lab_twin.domain.heartbeat import GpuSample, HeartbeatPayload
from gpu_lab_twin.domain.heartbeat_policy import check_boot_succession, reasons_from, validate_heartbeat
from gpu_lab_twin.domain.node import NodeSnapshot
from gpu_lab_twin.domain.node_state import ConnectivityStatus, DriverHealth, NodeState, ReasonCode

AT = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
SERVER = NodeSpec(
    node_id="central-gpu-server",
    kind=NodeKind.SERVER,
    heartbeat_interval_ms=10_000,
    storage_capacity_gb=4000,
    gpu_devices=(
        GpuDeviceSpec("central-gpu-server-gpu-0", 0, 48),
        GpuDeviceSpec("central-gpu-server-gpu-1", 1, 48),
    ),
)


def payload(**changes) -> HeartbeatPayload:
    base = HeartbeatPayload(
        event_id=uuid4(),
        occurred_at=AT,
        received_at=AT,
        schema_version="1.0",
        boot_session_id="boot-a",
        previous_boot_session_id=None,
        state_loss=False,
        source_sequence=1,
        gpu_samples=(
            GpuSample("central-gpu-server-gpu-0", 40.0, 10.0),
            GpuSample("central-gpu-server-gpu-1", 41.0, 48.0),
        ),
        driver_health=DriverHealth.HEALTHY,
        storage_free_gb=4000.0,
    )
    return replace(base, **changes)


def node(current_boot: str | None) -> NodeSnapshot:
    return NodeSnapshot(
        node_id=SERVER.node_id,
        kind=SERVER.kind,
        state=NodeState.HEALTHY,
        cordoned=False,
        connectivity=ConnectivityStatus.ONLINE,
        revision=3,
        evidence_epoch=0,
        current_boot_session_id=current_boot,
        heartbeat_interval_ms=10_000,
        last_accepted_event_at=AT,
        last_accepted_receive_at=AT,
        active_reason_codes=(),
    )


def code_of(call) -> ErrorCode:
    with pytest.raises(DomainError) as caught:
        call()
    return caught.value.code


def test_valid_dual_gpu_heartbeat_at_exact_capacity_is_accepted() -> None:
    validate_heartbeat(SERVER, payload(), AT)


@pytest.mark.parametrize(
    "samples",
    [
        (GpuSample("central-gpu-server-gpu-0", 40.0, 1.0),),
        (GpuSample("central-gpu-server-gpu-0", 40.0, 1.0), GpuSample("central-gpu-server-gpu-0", 40.0, 1.0)),
        (GpuSample("central-gpu-server-gpu-0", 40.0, 1.0), GpuSample("ws-gpu-01-gpu-0", 40.0, 1.0)),
    ],
    ids=["missing-gpu", "duplicate-gpu", "foreign-gpu"],
)
def test_gpu_membership_must_match_configuration_exactly(samples) -> None:
    assert code_of(lambda: validate_heartbeat(SERVER, payload(gpu_samples=samples), AT)) is ErrorCode.ERR_SCHEMA


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"storage_free_gb": 4000.001}, ErrorCode.ERR_CAPACITY_RANGE),
        (
            {
                "gpu_samples": (
                    GpuSample("central-gpu-server-gpu-0", 40.0, 48.5),
                    GpuSample("central-gpu-server-gpu-1", 40.0, 1.0),
                )
            },
            ErrorCode.ERR_CAPACITY_RANGE,
        ),
        (
            {
                "gpu_samples": (
                    GpuSample("central-gpu-server-gpu-0", float("inf"), 1.0),
                    GpuSample("central-gpu-server-gpu-1", 40.0, 1.0),
                )
            },
            ErrorCode.ERR_SCHEMA,
        ),
        ({"received_at": AT + timedelta(milliseconds=1)}, ErrorCode.ERR_SCHEMA),
    ],
    ids=["storage-over-capacity", "vram-over-capacity", "infinite-temperature", "receivedAt-in-future"],
)
def test_out_of_range_values_reject_the_whole_heartbeat(changes, expected) -> None:
    assert code_of(lambda: validate_heartbeat(SERVER, payload(**changes), AT)) is expected


def test_first_heartbeat_and_same_boot_need_no_succession_proof() -> None:
    assert check_boot_succession(node(current_boot=None), payload(boot_session_id="boot-z")) is False
    assert check_boot_succession(node(current_boot="boot-a"), payload()) is False


def test_unproven_boot_change_is_a_succession_error() -> None:
    assert code_of(lambda: check_boot_succession(node("boot-a"), payload(boot_session_id="boot-b"))) is (
        ErrorCode.ERR_BOOT_SUCCESSION
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"boot_session_id": "boot-b", "previous_boot_session_id": "boot-a"},
        {"boot_session_id": "boot-b", "state_loss": True},
        {"state_loss": True},
    ],
    ids=["linked-successor", "state-loss-new-boot", "state-loss-same-boot"],
)
def test_proven_reboot_starts_a_new_evidence_epoch(changes) -> None:
    assert check_boot_succession(node("boot-a"), payload(**changes)) is True


@pytest.mark.parametrize(
    ("driver", "expected"),
    [
        (DriverHealth.HEALTHY, frozenset()),
        (DriverHealth.UNHEALTHY, frozenset({ReasonCode.DRIVER_UNHEALTHY})),
        (DriverHealth.UNKNOWN, frozenset({ReasonCode.DRIVER_HEALTH_UNKNOWN})),
    ],
)
def test_driver_health_maps_to_reasons(driver, expected) -> None:
    assert reasons_from(payload(driver_health=driver)) == expected
