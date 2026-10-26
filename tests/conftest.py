from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from gpu_lab_twin.adapters.db.models import Base
from gpu_lab_twin.adapters.sim.fake_clock import FakeClock
from gpu_lab_twin.api.app import create_app
from gpu_lab_twin.bootstrap import Container, build_container
from gpu_lab_twin.config.settings import Settings

T0 = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


@pytest.fixture
def settings() -> Settings:
    return Settings(database_url="sqlite+pysqlite:///:memory:", policy_version="test-policy-v1")


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock(T0)


@pytest.fixture
def container(settings: Settings, fake_clock: FakeClock) -> Iterator[Container]:
    built = build_container(settings, clock=fake_clock)
    Base.metadata.create_all(built.engine)
    yield built
    built.engine.dispose()


@pytest.fixture
def client(container: Container) -> Iterator[TestClient]:
    with TestClient(create_app(container), raise_server_exceptions=False) as test_client:
        yield test_client
