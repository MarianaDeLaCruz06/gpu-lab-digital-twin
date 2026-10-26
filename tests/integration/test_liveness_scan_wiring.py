"""D1: the running service starts the periodic liveness scan and stops it cleanly on shutdown."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from gpu_lab_twin.adapters.db.models import Base
from gpu_lab_twin.api import app as app_module
from gpu_lab_twin.api.app import create_app
from gpu_lab_twin.bootstrap import build_container
from gpu_lab_twin.config.settings import Settings
from tests.conftest import TEST_DATABASE_URL


def test_service_schedules_the_liveness_scan_and_cancels_it_on_shutdown(monkeypatch, fake_clock) -> None:
    scheduled: dict = {}
    cancelled: list[bool] = []

    async def fake_run_periodically(task, period_seconds, **_kwargs):
        scheduled.update(task=task, period=period_seconds)
        task()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    monkeypatch.setattr(app_module, "run_periodically", fake_run_periodically)
    container = build_container(Settings(database_url=TEST_DATABASE_URL, liveness_scan_seconds=2.5), clock=fake_clock)
    Base.metadata.drop_all(container.engine)
    Base.metadata.create_all(container.engine)

    with TestClient(create_app(container)) as client:
        assert client.get("/health").status_code == 200

    assert scheduled["period"] == 2.5
    assert scheduled["task"] == container.liveness.evaluate_fleet_liveness
    assert cancelled == [True]
    container.engine.dispose()


def test_scan_is_on_by_default_every_5_seconds() -> None:
    assert Settings(database_url="sqlite+pysqlite:///:memory:").liveness_scan_seconds == 5.0


@pytest.mark.parametrize("seconds", [0.001, float("inf"), -1])
def test_busy_or_invalid_scan_periods_are_refused(seconds: float) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite+pysqlite:///:memory:", liveness_scan_seconds=seconds)
