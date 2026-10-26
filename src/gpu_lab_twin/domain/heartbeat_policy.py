"""Heartbeat acceptance rules: membership, ranges, boot succession, and reasons a sample activates."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from gpu_lab_twin.domain.errors import DomainError, ErrorCode
from gpu_lab_twin.domain.fleet import NodeSpec
from gpu_lab_twin.domain.heartbeat import HeartbeatPayload
from gpu_lab_twin.domain.node import NodeSnapshot
from gpu_lab_twin.domain.node_state import DriverHealth, ReasonCode

RECOVERY_POLICY_ID = "ODD-3"
SILENCE_INTERVALS = 3


def is_silent(last_accepted_receive_at: datetime | None, evaluation_at: datetime, interval_ms: int) -> bool:
    """AD-2: silent only when strictly more than three configured intervals passed since the last accepted receive.

    A node that never reported is not silent (it stays UNKNOWN); equality at the boundary is not silent.
    """
    if last_accepted_receive_at is None:
        return False
    return evaluation_at - last_accepted_receive_at > timedelta(milliseconds=SILENCE_INTERVALS * interval_ms)


def missed_intervals(last_accepted_receive_at: datetime, evaluation_at: datetime, interval_ms: int) -> float:
    return (evaluation_at - last_accepted_receive_at) / timedelta(milliseconds=interval_ms)


def validate_heartbeat(spec: NodeSpec, payload: HeartbeatPayload, at: datetime) -> None:
    """Reject the whole heartbeat if any part is invalid; nothing may be applied partially."""
    if payload.received_at > at:
        raise DomainError(
            ErrorCode.ERR_SCHEMA,
            f"Field receivedAt must not be later than the receive instant {at.isoformat()}.",
            details={"field": "receivedAt", "supplied": payload.received_at.isoformat(), "maximum": at.isoformat()},
        )

    reported = [sample.gpu_device_id for sample in payload.gpu_samples]
    configured = sorted(gpu.gpu_device_id for gpu in spec.gpu_devices)
    if sorted(reported) != configured:
        raise DomainError(
            ErrorCode.ERR_SCHEMA,
            f"Field gpuSamples must contain exactly the configured GPUs of {spec.node_id}.",
            details={"field": "gpuSamples", "supplied": reported, "expected": configured},
        )

    for index, sample in enumerate(payload.gpu_samples):
        gpu = spec.gpu(sample.gpu_device_id)
        assert gpu is not None  # membership was verified above
        if not math.isfinite(sample.temperature_c) or sample.temperature_c < 0:
            raise DomainError(
                ErrorCode.ERR_SCHEMA,
                f"Field gpuSamples[{index}].temperatureC must be a finite value >= 0.",
                details={"field": f"gpuSamples[{index}].temperatureC", "supplied": sample.temperature_c},
            )
        _require_within(
            f"gpuSamples[{index}].vramOccupiedGb", sample.vram_occupied_gb, gpu.vram_capacity_gb, gpu.gpu_device_id
        )

    _require_within("storageFreeGb", payload.storage_free_gb, spec.storage_capacity_gb, spec.node_id)


def check_boot_succession(node: NodeSnapshot, payload: HeartbeatPayload) -> None:
    """Fail closed on any reboot evidence; recovery handling (AD-6) is not enabled in this build."""
    current = node.current_boot_session_id
    if current is None:
        return
    changed = payload.boot_session_id != current
    proven = payload.state_loss or payload.previous_boot_session_id == current
    if changed and not proven:
        raise DomainError(
            ErrorCode.ERR_BOOT_SUCCESSION,
            f"Boot session {payload.boot_session_id} does not prove succession from {current}.",
            details={"bootSessionId": payload.boot_session_id, "currentBootSessionId": current},
        )
    if changed or payload.state_loss:
        raise DomainError(
            ErrorCode.ERR_POLICY_UNRESOLVED,
            f"Policy {RECOVERY_POLICY_ID} is unresolved; reboot evidence was not applied and the node state is held.",
            details={
                "policyId": RECOVERY_POLICY_ID,
                "bootSessionId": payload.boot_session_id,
                "currentBootSessionId": current,
            },
        )


def reasons_from(payload: HeartbeatPayload) -> frozenset[ReasonCode]:
    reasons: set[ReasonCode] = set()
    if payload.driver_health is DriverHealth.UNHEALTHY:
        reasons.add(ReasonCode.DRIVER_UNHEALTHY)
    elif payload.driver_health is DriverHealth.UNKNOWN:
        reasons.add(ReasonCode.DRIVER_HEALTH_UNKNOWN)
    return frozenset(reasons)


def _require_within(field: str, value: float, maximum: float, resource_id: str) -> None:
    if not math.isfinite(value) or value < 0 or value > maximum:
        raise DomainError(
            ErrorCode.ERR_CAPACITY_RANGE,
            f"{field}={value} is outside [0,{maximum}] for {resource_id}.",
            details={"field": field, "supplied": value, "maximum": maximum, "resourceId": resource_id},
        )
