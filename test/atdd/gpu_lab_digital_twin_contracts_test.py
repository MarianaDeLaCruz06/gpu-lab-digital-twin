"""Solu-2 executable RED suite.

Every test calls an explicit interface stub that raises NotImplementedError. Assertions describe
the required post-implementation contract and are intentionally not bypassed or skipped.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest

from test.atdd.stubs import EffectProbe, GpuLabDigitalTwinContractStub, TypedContractError


@pytest.fixture
def effects() -> EffectProbe:
    return EffectProbe()


@pytest.fixture
def twin(effects: EffectProbe) -> GpuLabDigitalTwinContractStub:
    return GpuLabDigitalTwinContractStub(effects)


def heartbeat_request(event_id, event, *, received_at=None, boot="boot-a", previous=None, state_loss=False):
    return {
        "eventId": event_id,
        "occurredAt": event.occurredAt,
        "receivedAt": received_at or event.occurredAt,
        "schemaVersion": "1.0",
        "bootSessionId": boot,
        "previousBootSessionId": previous,
        "stateLoss": state_loss,
        "sourceSequence": event.payload.get("sourceSequence", 1),
        "gpuSamples": [{"gpuDeviceId": f"{event.nodeId}-gpu-0", "temperatureC": event.payload.get("temperatureC", 40.0), "vramOccupiedGb": 0.0}],
        "driverHealth": "HEALTHY",
        "storageFreeGb": 400.0,
        "externalContext": None,
    }


@pytest.mark.asyncio
async def test_hb_fresh_001_valid_fresh_heartbeat_establishes_explainable_state(twin, fake_clock, sim_telemetry, explain_assert):
    event = sim_telemetry.heartbeat("ws-gpu-01", fake_clock.now(), sequence=1)
    result = await twin.ingestHeartbeat(event.nodeId, heartbeat_request(event.eventId, event), fake_clock.now())
    assert result["outcome"] == "APPLIED"
    assert result["state"] == "HEALTHY"
    assert result["cordoned"] is False
    explain_assert(result["explanation"], observed_key="driverHealth", expected_observed="HEALTHY", expected_state="HEALTHY")


@pytest.mark.asyncio
async def test_hb_invalid_001_unknown_node_has_typed_error_and_zero_effects(twin, effects, fake_clock, sim_telemetry):
    before = effects.snapshot()
    event = sim_telemetry.heartbeat("ws-gpu-99", fake_clock.now())
    with pytest.raises(TypedContractError) as caught:
        await twin.ingestHeartbeat(event.nodeId, heartbeat_request(event.eventId, event), fake_clock.now())
    assert (caught.value.code, caught.value.status) == ("ERR_UNKNOWN_NODE", 404)
    assert effects.snapshot() == before
    assert effects.forbidden_work_commands == []


@pytest.mark.asyncio
async def test_hb_order_001_stale_heartbeat_cannot_overwrite_newer_snapshot(twin, effects, fake_clock, sim_telemetry):
    newer = sim_telemetry.heartbeat("ws-gpu-02", fake_clock.now(), sequence=2)
    older = sim_telemetry.heartbeat("ws-gpu-02", fake_clock.now() - timedelta(seconds=5), sequence=1)
    applied = await twin.ingestHeartbeat(newer.nodeId, heartbeat_request(newer.eventId, newer), fake_clock.now())
    revision = applied["nodeRevision"]
    late = await twin.ingestHeartbeat(older.nodeId, heartbeat_request(older.eventId, older, received_at=fake_clock.now()), fake_clock.now())
    assert late["outcome"] == "LATE_IGNORED"
    assert late["nodeRevision"] == revision
    assert len(effects.history) <= 1


@pytest.mark.asyncio
async def test_hb_idem_001_duplicate_event_id_has_exactly_once_effects(twin, effects, fake_clock, sim_telemetry):
    event = sim_telemetry.heartbeat("ws-gpu-03", fake_clock.now())
    request = heartbeat_request(event.eventId, event)
    first = await twin.ingestHeartbeat(event.nodeId, request, fake_clock.now())
    counts = (len(effects.history), len(effects.audits), len(effects.events), len(effects.alerts))
    replay = await twin.ingestHeartbeat(event.nodeId, request, fake_clock.now())
    assert replay["outcome"] == "DUPLICATE"
    assert replay["nodeRevision"] == first["nodeRevision"]
    assert (len(effects.history), len(effects.audits), len(effects.events), len(effects.alerts)) == counts


def test_hb_silence_001_strict_more_than_three_intervals_transitions_offline(twin, fake_clock, explain_assert):
    interval = 10
    exactly_three = {"eventId": uuid4(), "occurredAt": fake_clock.advance(seconds=3 * interval), "schemaVersion": "1.0", "signalType": "CLOCK_EVALUATED", "evidenceId": "hb-1", "evaluationAt": fake_clock.now()}
    held = twin.transitionNodeState("ws-gpu-04", exactly_three)
    assert held["state"] != "OFFLINE"
    after_boundary = dict(exactly_three, eventId=uuid4(), occurredAt=fake_clock.advance(seconds=0.001), evaluationAt=fake_clock.now())
    offline = twin.transitionNodeState("ws-gpu-04", after_boundary)
    assert offline["state"] == "OFFLINE" and offline["cordoned"] is True
    explain_assert(offline["explanation"], observed_key="missedIntervals", expected_observed=3.0001, threshold_key="missedIntervals", expected_threshold={"operator": ">", "value": 3}, expected_state="OFFLINE")


@pytest.mark.asyncio
async def test_hb_thermal_001_over_88_degrades_and_cordons_with_evidence(twin, fake_clock, sim_telemetry, explain_assert):
    event = sim_telemetry.heartbeat("ws-gpu-14", fake_clock.now(), temperature_c=88.1)
    result = await twin.ingestHeartbeat(event.nodeId, heartbeat_request(event.eventId, event), fake_clock.now())
    assert result["state"] == "DEGRADED"
    assert result["cordoned"] is True
    explain_assert(result["explanation"], observed_key="temperatureC", expected_observed=88.1, threshold_key="temperatureC", expected_threshold={"operator": ">", "value": 88}, expected_state="DEGRADED")
    assert "ERR_THERMAL_88" in result["explanation"]["ruleIds"]


@pytest.mark.asyncio
async def test_hb_thermal_002_exactly_88_does_not_activate_thermal_rule(twin, fake_clock, sim_telemetry):
    event = sim_telemetry.heartbeat("ws-gpu-14", fake_clock.now(), temperature_c=88.0)
    result = await twin.ingestHeartbeat(event.nodeId, heartbeat_request(event.eventId, event), fake_clock.now())
    assert "ERR_THERMAL_88" not in result["explanation"]["ruleIds"]


@pytest.mark.asyncio
async def test_hb_reboot_001_ws_gpu_05_state_loss_enters_recovering(twin, fake_clock, sim_telemetry, explain_assert):
    event = sim_telemetry.reboot(fake_clock.now())
    result = await twin.ingestHeartbeat(event.nodeId, heartbeat_request(event.eventId, event, boot="boot-b", previous="boot-a", state_loss=True), fake_clock.now())
    assert result["outcome"] == "BOOT_CHANGE_DETECTED"
    assert result["state"] == "RECOVERING" and result["cordoned"] is True
    explain_assert(result["explanation"], observed_key="bootSessionId", expected_observed="boot-b", expected_state="RECOVERING")
    assert "ERR_STATE_LOSS" in result["explanation"]["ruleIds"]


def test_st_invalid_001_invalid_transition_is_typed_and_has_zero_mutation(twin, effects, fake_clock):
    before = effects.snapshot()
    signal = {"eventId": uuid4(), "occurredAt": fake_clock.now(), "schemaVersion": "1.0", "signalType": "HEARTBEAT_ACCEPTED", "evidenceId": "missing", "evaluationAt": fake_clock.now()}
    with pytest.raises(TypedContractError) as caught:
        twin.transitionNodeState("ws-gpu-01", signal)
    assert caught.value.code in {"ERR_EVIDENCE_NOT_FOUND", "ERR_INVALID_TRANSITION"}
    assert caught.value.status == 409
    assert effects.snapshot() == before


def test_st_precedence_001_all_conditions_select_one_fixed_precedence_state(twin, fake_clock):
    signal = {"eventId": uuid4(), "occurredAt": fake_clock.now(), "schemaVersion": "1.0", "signalType": "WORKLOAD_SNAPSHOT_ACCEPTED", "evidenceId": "all-at-once", "evaluationAt": fake_clock.now()}
    result = twin.transitionNodeState("central-gpu-server", signal)
    assert result["state"] == "DRAINING"
    assert result["transitioned"] is True
    assert {"ERR_THERMAL_88", "ERR_STATE_LOSS", "ERR_SILENT"}.issubset(set(result["activeReasonCodes"]))


def test_st_flap_001_p0_five_second_flapping_is_evidence_only_and_bounded(twin, effects, fake_clock, sim_telemetry):
    baseline = {"state": "HEALTHY", "cordoned": False, "connectivityStatus": "ONLINE"}
    observations = sim_telemetry.flapping("ws-gpu-07", fake_clock.now(), observations=12)
    public_tuples = []
    for observation in observations:
        fake_clock.advance(seconds=0 if observation == observations[0] else 5)
        result = twin.transitionNodeState(observation.nodeId, {"eventId": observation.eventId, "occurredAt": observation.occurredAt, "schemaVersion": "1.0", "signalType": "CONNECTIVITY_OBSERVED", "evidenceId": str(observation.eventId), "evaluationAt": fake_clock.now(), "connectivityObservation": observation.payload["status"]})
        public_tuples.append((result["state"], result["cordoned"], result["connectivityStatus"]))
        assert "ERR_POLICY_UNRESOLVED" in result["explanation"]["ruleIds"]
        assert "ODD-5" in result["explanation"]["thresholds"] or result["explanation"]["expectedState"] == "HEALTHY"
    assert set(public_tuples) == {(baseline["state"], baseline["cordoned"], baseline["connectivityStatus"])}
    assert len([a for a in effects.alerts if a.get("reasonCode") == "ERR_CONNECTIVITY_FLAPPING" and a.get("closedAt") is None]) == 0
    assert len([a for a in effects.alerts if a.get("reasonCode") == "ERR_POLICY_UNRESOLVED" and a.get("closedAt") is None]) <= 1


def test_st_explain_001_every_automated_decision_has_structured_explanation(twin, fake_clock, explain_assert):
    signal = {"eventId": uuid4(), "occurredAt": fake_clock.now(), "schemaVersion": "1.0", "signalType": "CLOCK_EVALUATED", "evidenceId": "tick-1", "evaluationAt": fake_clock.now()}
    result = twin.transitionNodeState("ws-gpu-08", signal)
    explain_assert(result["explanation"], observed_key="evaluationAt", expected_observed=fake_clock.now(), threshold_key="missedIntervals", expected_threshold={"operator": ">", "value": 3}, expected_state=result["state"])


@pytest.mark.asyncio
async def test_mt_happy_001_valid_drain_immediately_cordons_and_preserves_work_context(twin, effects, fake_clock):
    window = {"eventId": uuid4(), "requestId": uuid4(), "occurredAt": fake_clock.now(), "schemaVersion": "1.0", "startsAt": fake_clock.now(), "reason": "Replace simulated cooling fan", "expectedNodeRevision": 4, "actor": "Carlos"}
    result = await twin.scheduleMaintenanceDrain("central-gpu-server", window)
    assert result["state"] == "DRAINING" and result["cordoned"] is True
    assert result["activeWorkloadCount"] == len(result["activeWorkloadIds"])
    assert effects.forbidden_work_commands == []


@pytest.mark.asyncio
async def test_mt_invalid_001_invalid_drain_has_typed_error_and_zero_effects(twin, effects, fake_clock):
    before = effects.snapshot()
    window = {"eventId": uuid4(), "requestId": uuid4(), "occurredAt": fake_clock.now(), "schemaVersion": "1.0", "startsAt": fake_clock.now(), "reason": "", "expectedNodeRevision": 0, "actor": "Carlos"}
    with pytest.raises(TypedContractError) as caught:
        await twin.scheduleMaintenanceDrain("central-gpu-server", window)
    assert (caught.value.code, caught.value.status) == ("ERR_SCHEMA", 422)
    assert effects.snapshot() == before
    assert effects.forbidden_work_commands == []


@pytest.mark.asyncio
async def test_mt_conc_001_concurrent_identical_drain_creates_one_lock_and_event(twin, effects, fake_clock):
    window = {"eventId": uuid4(), "requestId": uuid4(), "occurredAt": fake_clock.now(), "schemaVersion": "1.0", "startsAt": fake_clock.now(), "reason": "Inspect server", "expectedNodeRevision": 9, "actor": "Carlos"}
    first, second = await asyncio.gather(twin.scheduleMaintenanceDrain("central-gpu-server", window), twin.scheduleMaintenanceDrain("central-gpu-server", window))
    assert {first["outcome"], second["outcome"]} == {"SCHEDULED", "DUPLICATE"}
    assert first["lockId"] == second["lockId"]
    assert len(effects.locks) == 1
    assert len([event for event in effects.events if event.get("eventType") == "MaintenanceDrainScheduled"]) == 1


@pytest.mark.asyncio
async def test_mt_stale_001_pre_lock_zero_cannot_complete_drain(twin, fake_clock):
    window = {"eventId": uuid4(), "requestId": uuid4(), "occurredAt": fake_clock.now(), "schemaVersion": "1.0", "startsAt": fake_clock.now(), "reason": "Inspect server", "expectedNodeRevision": 2, "actor": "Carlos", "workloadEvidence": {"source": "EXTERNAL_MOCK", "activeWorkloadCount": 0, "activeWorkloadIds": [], "observedAt": fake_clock.now() - timedelta(seconds=1), "receivedAt": fake_clock.now()}}
    result = await twin.scheduleMaintenanceDrain("central-gpu-server", window)
    assert result["state"] == "DRAINING"
    assert "DRAIN_STATUS_UNKNOWN" in result["explanation"]["ruleIds"]


@pytest.mark.asyncio
async def test_mt_explain_001_drain_explanation_has_expected_state_and_workload_value(twin, fake_clock, explain_assert):
    window = {"eventId": uuid4(), "requestId": uuid4(), "occurredAt": fake_clock.now(), "schemaVersion": "1.0", "startsAt": fake_clock.now(), "reason": "Inspect server", "expectedNodeRevision": 6, "actor": "Carlos"}
    result = await twin.scheduleMaintenanceDrain("central-gpu-server", window)
    explain_assert(result["explanation"], observed_key="activeWorkloadCount", expected_observed=result["activeWorkloadCount"], expected_state=result["state"])


@pytest.mark.asyncio
async def test_sc_isolation_001_invalid_gpu_identifier_cannot_mutate_other_node(twin, effects, fake_clock, sim_telemetry):
    before = effects.snapshot()
    event = sim_telemetry.heartbeat("ws-gpu-09", fake_clock.now())
    request = heartbeat_request(event.eventId, event)
    request["gpuSamples"][0]["gpuDeviceId"] = "ws-gpu-10-gpu-0"
    with pytest.raises(TypedContractError) as caught:
        await twin.ingestHeartbeat("ws-gpu-09", request, fake_clock.now())
    assert caught.value.code == "ERR_SCHEMA"
    assert effects.snapshot() == before
