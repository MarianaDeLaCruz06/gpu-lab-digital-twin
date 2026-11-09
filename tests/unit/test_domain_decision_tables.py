"""Exhaustive, table-driven unit tests for the pure domain rules (no database, no network, no clock).

These pin every boundary the AD-n invariants name, so the bulk of the suite stays fast and isolated
(70/20/10 pyramid): AD-4 reducer precedence, AD-3 thermal edge, AD-2 silence edge, capacity ranges,
AD-6 boot succession, AD-7 drain completion and the Story 3.5 10 Hz window bucketing.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from itertools import combinations
from uuid import uuid4

import pytest

from gpu_lab_twin.domain.errors import DomainError, ErrorCode
from gpu_lab_twin.domain.heartbeat import GpuSample
from gpu_lab_twin.domain.heartbeat_policy import (
    THERMAL_THRESHOLD_C,
    check_boot_succession,
    is_silent,
    reasons_from,
    validate_heartbeat,
)
from gpu_lab_twin.domain.maintenance import WorkloadSnapshot, maintenance_state
from gpu_lab_twin.domain.node_state import DEGRADATION_REASONS, NodeFacts, NodeState, ReasonCode, evaluate
from gpu_lab_twin.domain.telemetry_downsampling import TelemetryDownsampler
from tests.unit.test_heartbeat_policy import AT, SERVER, node, payload

# --- AD-4: the complete reducer decision table --------------------------------------------------------------

ALL_REASON_SETS = [frozenset(combo) for size in range(len(ReasonCode) + 1) for combo in combinations(ReasonCode, size)]
MAINTENANCE_MODES = {
    "none": {"maintenance_active": False, "active_workload_count": None},
    "draining": {"maintenance_active": True, "active_workload_count": None},
    "fresh-zero": {"maintenance_active": True, "active_workload_count": 0},
}


def _expected_state(reasons: frozenset[ReasonCode], heartbeat: bool, mode: str) -> NodeState:
    """AD-4 precedence written as an ordered table, independent of the reducer's if/elif chain."""
    precedence = (
        (mode == "draining", NodeState.DRAINING),
        (mode == "fresh-zero", NodeState.MAINTENANCE),
        (ReasonCode.SILENT in reasons, NodeState.OFFLINE),
        (ReasonCode.RECOVERY_PENDING in reasons, NodeState.RECOVERING),
        (bool(reasons & DEGRADATION_REASONS), NodeState.DEGRADED),
        (heartbeat, NodeState.HEALTHY),
    )
    return next((state for applies, state in precedence if applies), NodeState.UNKNOWN)


@pytest.mark.parametrize("mode", list(MAINTENANCE_MODES))
@pytest.mark.parametrize("heartbeat", [True, False], ids=["heartbeat", "no-heartbeat"])
@pytest.mark.parametrize("reasons", ALL_REASON_SETS, ids=lambda r: "+".join(sorted(r)) or "no-reason")
def test_reducer_selects_exactly_one_state_by_ad4_precedence(
    reasons: frozenset[ReasonCode], heartbeat: bool, mode: str
) -> None:
    decision = evaluate(NodeFacts(has_current_heartbeat=heartbeat, reasons=reasons, **MAINTENANCE_MODES[mode]))

    expected = _expected_state(reasons, heartbeat, mode)
    assert decision.state is expected
    # Only a clean HEALTHY node is eligible for new work; any active reason keeps it cordoned.
    assert decision.cordoned is (expected is not NodeState.HEALTHY or bool(reasons))
    # Lower-precedence reasons are retained as evidence, never dropped.
    assert decision.reason_codes == tuple(sorted(reasons))
    assert decision.rule_ids, "every decision cites at least one rule"


# --- AD-3: thermal threshold is strictly greater than 88 °C ---------------------------------------------------


@pytest.mark.parametrize(
    ("hottest", "thermal"),
    [
        (0.0, False),
        (45.0, False),
        (87.99, False),
        (float(THERMAL_THRESHOLD_C), False),
        (88.0001, True),
        (88.1, True),
        (95.0, True),
        (120.0, True),
    ],
)
@pytest.mark.parametrize("hot_gpu", [0, 1], ids=["gpu-0-hot", "gpu-1-hot"])
def test_thermal_reason_activates_only_strictly_above_88c_on_any_gpu(
    hottest: float, thermal: bool, hot_gpu: int
) -> None:
    temperatures = [40.0, 40.0]
    temperatures[hot_gpu] = hottest
    samples = tuple(
        GpuSample(f"central-gpu-server-gpu-{index}", temperature, 1.0) for index, temperature in enumerate(temperatures)
    )

    assert (ReasonCode.THERMAL in reasons_from(payload(gpu_samples=samples))) is thermal


# --- AD-2: silence needs strictly more than three configured intervals ---------------------------------------


@pytest.mark.parametrize("interval_ms", [1_000, 10_000, 30_000])
@pytest.mark.parametrize(
    ("elapsed_offset_ms", "silent"),
    [(-1_000, False), (-1, False), (0, False), (1, True), (1_000, True)],
    ids=["well-before", "1ms-before", "exact-boundary", "1ms-after", "well-after"],
)
def test_silence_boundary_is_exclusive_at_three_intervals(
    interval_ms: int, elapsed_offset_ms: int, silent: bool
) -> None:
    evaluated_at = AT + timedelta(milliseconds=3 * interval_ms + elapsed_offset_ms)

    assert is_silent(AT, evaluated_at, interval_ms) is silent


@pytest.mark.parametrize("interval_ms", [1_000, 10_000])
def test_a_node_that_never_reported_is_never_silent(interval_ms: int) -> None:
    assert is_silent(None, AT + timedelta(days=1), interval_ms) is False


# --- Capacity ranges: whole heartbeat rejected, typed error, nothing partial ---------------------------------


@pytest.mark.parametrize(
    ("vram", "accepted"),
    [
        (0.0, True),
        (24.0, True),
        (48.0, True),
        (-0.01, False),
        (48.01, False),
        (float("nan"), False),
        (float("inf"), False),
    ],
)
def test_vram_must_stay_within_the_configured_gpu_capacity(vram: float, accepted: bool) -> None:
    samples = (GpuSample("central-gpu-server-gpu-0", 40.0, vram), GpuSample("central-gpu-server-gpu-1", 40.0, 1.0))
    heartbeat = payload(gpu_samples=samples)

    if accepted:
        validate_heartbeat(SERVER, heartbeat, AT)
    else:
        with pytest.raises(DomainError) as rejected:
            validate_heartbeat(SERVER, heartbeat, AT)
        assert rejected.value.code is ErrorCode.ERR_CAPACITY_RANGE
        assert rejected.value.details["field"] == "gpuSamples[0].vramOccupiedGb"


@pytest.mark.parametrize(
    ("storage", "accepted"),
    [(0.0, True), (2000.0, True), (4000.0, True), (-1.0, False), (4000.5, False), (float("nan"), False)],
)
def test_storage_free_must_stay_within_node_capacity(storage: float, accepted: bool) -> None:
    heartbeat = payload(storage_free_gb=storage)

    if accepted:
        validate_heartbeat(SERVER, heartbeat, AT)
    else:
        with pytest.raises(DomainError) as rejected:
            validate_heartbeat(SERVER, heartbeat, AT)
        assert rejected.value.code is ErrorCode.ERR_CAPACITY_RANGE


@pytest.mark.parametrize("temperature", [-0.1, float("nan"), float("inf"), float("-inf")])
def test_non_finite_or_negative_temperature_is_a_schema_error(temperature: float) -> None:
    samples = (
        GpuSample("central-gpu-server-gpu-0", temperature, 1.0),
        GpuSample("central-gpu-server-gpu-1", 40.0, 1.0),
    )

    with pytest.raises(DomainError) as rejected:
        validate_heartbeat(SERVER, payload(gpu_samples=samples), AT)
    assert rejected.value.code is ErrorCode.ERR_SCHEMA


@pytest.mark.parametrize(
    "gpu_ids",
    [
        ("central-gpu-server-gpu-0",),
        ("central-gpu-server-gpu-0", "central-gpu-server-gpu-0"),
        ("central-gpu-server-gpu-0", "central-gpu-server-gpu-2"),
        ("central-gpu-server-gpu-0", "central-gpu-server-gpu-1", "central-gpu-server-gpu-2"),
    ],
    ids=["missing-gpu", "duplicate-gpu", "foreign-gpu", "extra-gpu"],
)
def test_gpu_samples_must_match_the_configured_devices_exactly(gpu_ids: tuple[str, ...]) -> None:
    samples = tuple(GpuSample(gpu_id, 40.0, 1.0) for gpu_id in gpu_ids)

    with pytest.raises(DomainError) as rejected:
        validate_heartbeat(SERVER, payload(gpu_samples=samples), AT)
    assert rejected.value.code is ErrorCode.ERR_SCHEMA
    assert rejected.value.details["field"] == "gpuSamples"


@pytest.mark.parametrize(("skew_ms", "accepted"), [(-1_000, True), (0, True), (1, False), (60_000, False)])
def test_received_at_may_not_be_later_than_the_receive_instant(skew_ms: int, accepted: bool) -> None:
    heartbeat = payload(received_at=AT + timedelta(milliseconds=skew_ms))

    if accepted:
        validate_heartbeat(SERVER, heartbeat, AT)
    else:
        with pytest.raises(DomainError) as rejected:
            validate_heartbeat(SERVER, heartbeat, AT)
        assert rejected.value.details["field"] == "receivedAt"


# --- AD-6: boot succession -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "boot", "previous", "state_loss", "outcome"),
    [
        (None, "boot-a", None, False, False),
        ("boot-a", "boot-a", None, False, False),
        ("boot-a", "boot-a", None, True, True),
        ("boot-a", "boot-b", "boot-a", False, True),
        ("boot-a", "boot-b", None, True, True),
        ("boot-a", "boot-b", None, False, "reject"),
        ("boot-a", "boot-b", "boot-z", False, "reject"),
    ],
    ids=[
        "first-boot",
        "same-boot",
        "same-boot-state-loss",
        "proven-successor",
        "explicit-loss",
        "unproven",
        "wrong-link",
    ],
)
def test_boot_succession_decision_table(current, boot, previous, state_loss, outcome) -> None:
    heartbeat = payload(boot_session_id=boot, previous_boot_session_id=previous, state_loss=state_loss)

    if outcome == "reject":
        with pytest.raises(DomainError) as rejected:
            check_boot_succession(node(current), heartbeat)
        assert rejected.value.code is ErrorCode.ERR_BOOT_SUCCESSION
    else:
        assert check_boot_succession(node(current), heartbeat) is outcome


# --- AD-7: a drain completes only on a fresh, post-lock, zero-workload snapshot -------------------------------


def _snapshot(*, observed_delta_s: int, received_delta_s: int, workloads: int) -> WorkloadSnapshot:
    return WorkloadSnapshot(
        event_id=uuid4(),
        snapshot_id=uuid4(),
        node_id=SERVER.node_id,
        source_revision=1,
        observed_at=AT + timedelta(seconds=observed_delta_s),
        received_at=AT + timedelta(seconds=received_delta_s),
        active_workload_ids=tuple(f"job-{index}" for index in range(workloads)),
    )


@pytest.mark.parametrize(
    ("observed", "received", "workloads", "expected"),
    [
        (1, 1, 0, NodeState.MAINTENANCE),
        (0, 0, 0, NodeState.MAINTENANCE),
        (1, 1, 1, NodeState.DRAINING),
        (1, 1, 5, NodeState.DRAINING),
        (-1, 1, 0, NodeState.DRAINING),
        (1, -1, 0, NodeState.DRAINING),
        (-5, -5, 0, NodeState.DRAINING),
    ],
    ids=["fresh-zero", "same-instant-zero", "one-job", "five-jobs", "observed-pre-lock", "received-pre-lock", "stale"],
)
def test_drain_completion_requires_fresh_post_lock_zero_workload(observed, received, workloads, expected) -> None:
    snapshot = _snapshot(observed_delta_s=observed, received_delta_s=received, workloads=workloads)

    assert maintenance_state(lock_acquired_at=AT, snapshot=snapshot) is expected


def test_drain_without_any_snapshot_stays_draining() -> None:
    assert maintenance_state(lock_acquired_at=AT, snapshot=None) is NodeState.DRAINING


# --- Story 3.5: 10 Hz window bucketing keeps the exact peak ----------------------------------------------------


@pytest.mark.parametrize(
    ("first_us", "second_us", "same_window"),
    [
        (0, 99_999, True),
        (0, 100_000, False),
        (50_000, 99_999, True),
        (99_999, 100_000, False),
        (100_000, 199_999, True),
        (900_000, 999_999, True),
    ],
)
def test_samples_share_a_window_only_inside_the_same_100ms_bucket(
    first_us: int, second_us: int, same_window: bool
) -> None:
    downsampler = TelemetryDownsampler(frequency_hz=10, capacity_windows=10)
    hot = (GpuSample("central-gpu-server-gpu-0", 80.0, 1.0), GpuSample("central-gpu-server-gpu-1", 40.0, 1.0))
    cool = (GpuSample("central-gpu-server-gpu-0", 50.0, 1.0), GpuSample("central-gpu-server-gpu-1", 40.0, 1.0))

    downsampler.observe(SERVER.node_id, payload(occurred_at=AT.replace(microsecond=first_us), gpu_samples=hot))
    window = downsampler.observe(
        SERVER.node_id, payload(occurred_at=AT.replace(microsecond=second_us), gpu_samples=cool)
    )

    assert (downsampler.retained_windows == 1) is same_window
    assert window.ends_at - window.starts_at == timedelta(milliseconds=100)
    expected_peak = 80.0 if same_window else 50.0
    assert window.gpus[0].peak_temperature_c == expected_peak


@pytest.mark.parametrize("frequency_hz", [1, 5, 10, 20])
def test_window_length_is_the_inverse_of_the_target_frequency(frequency_hz: int) -> None:
    window = TelemetryDownsampler(frequency_hz=frequency_hz).observe(SERVER.node_id, payload())

    assert window.ends_at - window.starts_at == timedelta(seconds=1) / frequency_hz


@pytest.mark.parametrize(("frequency_hz", "capacity"), [(0, 10), (-1, 10), (10, 0), (10, -5)])
def test_downsampler_rejects_non_positive_configuration(frequency_hz: int, capacity: int) -> None:
    with pytest.raises(ValueError):
        TelemetryDownsampler(frequency_hz=frequency_hz, capacity_windows=capacity)


def test_payload_builder_is_isolated_from_other_tests() -> None:
    """Guard: the shared builder must hand out independent payloads (no shared mutable state)."""
    first, second = payload(), payload()
    assert first.event_id != second.event_id
    assert replace(first, storage_free_gb=1.0).storage_free_gb == 1.0
    assert first.storage_free_gb == 4000.0
