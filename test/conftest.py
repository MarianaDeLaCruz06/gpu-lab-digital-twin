from datetime import datetime, timezone
from pathlib import Path

import pytest

from test.fixtures.db import EphemeralPostgresPlan
from test.fixtures.explain_assert import assert_explanation as explanation_assertion
from test.fixtures.fake_clock import FakeClock
from test.fixtures.seed_fleet import canonical_seed_fleet
from test.fixtures.sim_telemetry import SimTelemetry


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock(datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc))


@pytest.fixture
def seed_fleet():
    fleet = canonical_seed_fleet()
    assert len(fleet) == 32
    assert sum(len(node.gpuDevices) for node in fleet) == 33
    assert sum(gpu.vramCapacityGb for node in fleet for gpu in node.gpuDevices) == 840
    assert all(node.state == "HEALTHY" and node.cordoned is False for node in fleet)
    return fleet


@pytest.fixture
def sim_telemetry() -> SimTelemetry:
    return SimTelemetry()


@pytest.fixture
def db() -> EphemeralPostgresPlan:
    plan = EphemeralPostgresPlan(Path("planning/detailed-design/schemas/001_gpu_lab_digital_twin_schema.sql"))
    plan.assert_ready_for_implementation()
    return plan


@pytest.fixture
def explain_assert():
    return explanation_assertion
