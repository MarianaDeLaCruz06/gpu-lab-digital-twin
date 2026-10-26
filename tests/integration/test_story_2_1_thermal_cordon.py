"""Story 2.1 (task annex 3.3): automated thermal anomaly cordoning (AD-3, strict > 88 °C)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from gpu_lab_twin.adapters.db.models import AlertRow, NodeRow, NodeStateHistoryRow
from gpu_lab_twin.bootstrap import Container
from tests.conftest import T0
from tests.support import assert_matches_contract, heartbeat_body

THERMAL_THRESHOLD = {"operator": ">", "value": 88}


def beat(client: TestClient, node_id: str, at, seq: int = 1, **overrides) -> dict:
    response = client.post(f"/v1/nodes/{node_id}/heartbeats", json=heartbeat_body(node_id, at, seq=seq, **overrides))
    assert response.status_code == 200, response.text
    body = response.json()
    assert_matches_contract("IngestHeartbeatResponse", body)
    return body


def alert_rows(container: Container, node_id: str) -> list[tuple[str, int, bool]]:
    with container.engine.connect() as connection:
        rows = connection.execute(select(AlertRow).where(AlertRow.node_id == node_id).order_by(AlertRow.reason_code))
        return [(row.reason_code, row.update_count, row.closed_at is None) for row in rows]


def fleet_entry(client: TestClient, node_id: str) -> dict:
    return next(node for node in client.get("/v1/nodes").json()["nodes"] if node["nodeId"] == node_id)


# Annex scenario: Given "ws-gpu-19" is currently ONLINE, When a heartbeat is received with GPU temperature 91 °C,
# Then it is immediately transitioned to CORDONED_THERMAL (contract: DEGRADED + cordoned) and flagged unavailable.
def test_thermal_emergency_cordons_immediately_and_is_visible_as_unavailable(
    client: TestClient, container: Container, fake_clock
) -> None:
    healthy = beat(client, "ws-gpu-19", T0)
    assert (healthy["state"], healthy["cordoned"]) == ("HEALTHY", False)

    hot = beat(client, "ws-gpu-19", fake_clock.advance(seconds=10), seq=2, temperatures=(91.0,))

    assert (hot["state"], hot["cordoned"], hot["connectivityStatus"]) == ("DEGRADED", True, "ONLINE")
    explanation = hot["explanation"]
    assert explanation["ruleIds"] == ["ERR_THERMAL_88"]
    assert explanation["thresholds"] == {"temperatureC": THERMAL_THRESHOLD}
    assert explanation["observedValues"]["temperatureC"] == 91.0
    assert explanation["observedValues"]["hottestGpuDeviceId"] == "ws-gpu-19-gpu-0"
    assert (explanation["priorState"], explanation["resultState"]) == ("HEALTHY", "DEGRADED")
    assert alert_rows(container, "ws-gpu-19") == [("ERR_THERMAL_88", 1, True)]

    entry = fleet_entry(client, "ws-gpu-19")
    assert (entry["state"], entry["cordoned"], entry["activeReasonCodes"]) == ("DEGRADED", True, ["ERR_THERMAL_88"])

    with container.engine.connect() as connection:
        transition = connection.execute(
            select(NodeStateHistoryRow)
            .where(NodeStateHistoryRow.node_id == "ws-gpu-19")
            .order_by(NodeStateHistoryRow.node_revision.desc())
        ).first()
    assert (transition.prior_state, transition.result_state, transition.result_cordoned) == (
        "HEALTHY",
        "DEGRADED",
        True,
    )
    assert transition.rule_ids == ["ERR_THERMAL_88"]


def test_just_above_88_activates_the_rule(client: TestClient, container: Container) -> None:
    body = beat(client, "ws-gpu-14", T0, temperatures=(88.1,))

    assert (body["state"], body["cordoned"]) == ("DEGRADED", True)
    assert "ERR_THERMAL_88" in body["explanation"]["ruleIds"]
    assert body["explanation"]["observedValues"]["temperatureC"] == 88.1


def test_exactly_88_does_not_activate_the_rule(client: TestClient, container: Container) -> None:
    body = beat(client, "ws-gpu-14", T0, temperatures=(88.0,))

    assert (body["state"], body["cordoned"]) == ("HEALTHY", False)
    assert "ERR_THERMAL_88" not in body["explanation"]["ruleIds"]
    assert body["explanation"]["thresholds"] == {}
    assert alert_rows(container, "ws-gpu-14") == []


def test_one_hot_server_gpu_cordons_the_whole_node(client: TestClient, container: Container) -> None:
    body = beat(client, "central-gpu-server", T0, temperatures=(91.0, 40.0), vram_gb=(1.0, 1.0))

    assert (body["state"], body["cordoned"]) == ("DEGRADED", True)
    assert body["explanation"]["observedValues"]["hottestGpuDeviceId"] == "central-gpu-server-gpu-0"
    assert fleet_entry(client, "central-gpu-server")["cordoned"] is True


def test_hot_first_heartbeat_goes_from_unknown_to_degraded(client: TestClient, container: Container) -> None:
    body = beat(client, "ws-gpu-20", T0, temperatures=(95.0,))

    assert (body["explanation"]["priorState"], body["state"], body["cordoned"]) == ("UNKNOWN", "DEGRADED", True)


def test_cooling_down_keeps_the_cordon_until_a_release_policy_exists(
    client: TestClient, container: Container, fake_clock
) -> None:
    hot = beat(client, "ws-gpu-19", T0, temperatures=(91.0,))

    cool = beat(client, "ws-gpu-19", fake_clock.advance(seconds=10), seq=2, temperatures=(70.0,))

    assert (cool["state"], cool["cordoned"]) == ("DEGRADED", True)
    explanation = cool["explanation"]
    assert explanation["ruleIds"] == ["ERR_THERMAL_88", "ERR_POLICY_UNRESOLVED"]
    assert explanation["observedValues"]["temperatureC"] == 70.0
    assert explanation["observedValues"]["retainedReasonEvidence"] == {"ERR_THERMAL_88": [hot["eventId"]]}
    assert explanation["observedValues"]["activatingTemperatureC"] == 91.0
    assert explanation["observedValues"]["activatingGpuDeviceId"] == "ws-gpu-19-gpu-0"
    assert explanation["thresholds"] == {
        "temperatureC": THERMAL_THRESHOLD,
        "clearPolicy": {"ERR_THERMAL_88": {"policyId": "ODD-4", "status": "unresolved"}},
    }
    assert alert_rows(container, "ws-gpu-19") == [("ERR_THERMAL_88", 1, True)], (
        "a cool reading is not a new observation"
    )
    assert fleet_entry(client, "ws-gpu-19")["cordoned"] is True, "never eligible while the thermal reason is active"


def test_thermal_and_driver_reasons_are_both_cited(client: TestClient, container: Container) -> None:
    body = beat(client, "ws-gpu-21", T0, temperatures=(91.0,), driver="UNKNOWN")

    assert (body["state"], body["cordoned"]) == ("DEGRADED", True)
    assert body["explanation"]["ruleIds"] == ["ERR_DRIVER_HEALTH_UNKNOWN", "ERR_THERMAL_88"]
    assert body["explanation"]["thresholds"] == {
        "driverHealth": {"operator": "==", "value": "HEALTHY"},
        "temperatureC": THERMAL_THRESHOLD,
    }
    assert [reason for reason, _, is_open in alert_rows(container, "ws-gpu-21") if is_open] == [
        "ERR_DRIVER_HEALTH_UNKNOWN",
        "ERR_THERMAL_88",
    ]


def test_hot_heartbeat_returning_after_offline_is_recovering_with_thermal_active(
    client: TestClient, container: Container, fake_clock
) -> None:
    beat(client, "ws-gpu-22", T0)
    fake_clock.advance(seconds=45)
    container.liveness.evaluate_fleet_liveness()

    body = beat(client, "ws-gpu-22", fake_clock.advance(seconds=1), seq=2, temperatures=(91.0,))

    assert (body["state"], body["cordoned"]) == ("RECOVERING", True)
    assert body["explanation"]["thresholds"]["temperatureC"] == THERMAL_THRESHOLD
    assert body["explanation"]["ruleIds"] == ["RECOVERY_PENDING"], "RECOVERING outranks DEGRADED"
    open_reasons = {reason for reason, _, is_open in alert_rows(container, "ws-gpu-22") if is_open}
    assert open_reasons == {"ERR_THERMAL_88", "RECOVERY_PENDING"}
    entry = fleet_entry(client, "ws-gpu-22")
    assert sorted(entry["activeReasonCodes"]) == ["ERR_THERMAL_88", "RECOVERY_PENDING"], "silence cleared"


def test_hot_node_that_goes_silent_keeps_its_thermal_reason(
    client: TestClient, container: Container, fake_clock
) -> None:
    hot = beat(client, "ws-gpu-23", T0, temperatures=(91.0,))
    fake_clock.advance(seconds=31)

    container.liveness.evaluate_fleet_liveness()

    with container.engine.connect() as connection:
        row = connection.execute(select(NodeRow).where(NodeRow.node_id == "ws-gpu-23")).one()
        silence = connection.execute(
            select(NodeStateHistoryRow)
            .where(NodeStateHistoryRow.node_id == "ws-gpu-23")
            .order_by(NodeStateHistoryRow.node_revision.desc())
        ).first()
    assert (row.state, row.cordoned, set(row.active_reason_codes)) == (
        "OFFLINE",
        True,
        {"ERR_SILENT", "ERR_THERMAL_88"},
    )
    assert silence.explanation["observedValues"]["retainedReasonEvidence"] == {"ERR_THERMAL_88": [hot["eventId"]]}


def test_second_gpu_overheating_is_named_in_the_explanation(client: TestClient, container: Container) -> None:
    body = beat(client, "central-gpu-server", T0, temperatures=(40.0, 91.0), vram_gb=(1.0, 1.0))

    assert (body["state"], body["cordoned"]) == ("DEGRADED", True)
    assert body["explanation"]["observedValues"]["hottestGpuDeviceId"] == "central-gpu-server-gpu-1"
    assert body["explanation"]["observedValues"]["temperatureC"] == 91.0


def test_repeated_hot_readings_update_one_episode(client: TestClient, container: Container, fake_clock) -> None:
    beat(client, "ws-gpu-24", T0, temperatures=(91.0,))

    again = beat(client, "ws-gpu-24", fake_clock.advance(seconds=10), seq=2, temperatures=(93.5,))

    assert (again["state"], again["cordoned"]) == ("DEGRADED", True)
    assert again["explanation"]["ruleIds"] == ["ERR_THERMAL_88"], "still observed: nothing is merely retained"
    assert alert_rows(container, "ws-gpu-24") == [("ERR_THERMAL_88", 2, True)]


def test_sub_precision_reading_is_judged_on_the_stored_value(client: TestClient, container: Container) -> None:
    body = beat(client, "ws-gpu-25", T0, temperatures=(88.0004,))

    assert (body["state"], body["cordoned"]) == ("HEALTHY", False), "88.0004 is stored as 88.000, which is not > 88"
    assert body["explanation"]["observedValues"]["temperatureC"] == 88.0
    assert fleet_entry(client, "ws-gpu-25")["gpus"][0]["temperatureC"] == 88.0

    hot = beat(client, "ws-gpu-26", T0, temperatures=(88.0006,))
    assert (hot["state"], hot["explanation"]["observedValues"]["temperatureC"]) == ("DEGRADED", 88.001)
    assert fleet_entry(client, "ws-gpu-26")["gpus"][0]["temperatureC"] == 88.001
