from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from hypothesis import settings as hypothesis_settings
from sqlalchemy.engine import make_url

from gpu_lab_twin.adapters.db.models import Base
from gpu_lab_twin.adapters.sim.fake_clock import FakeClock
from gpu_lab_twin.api.app import create_app
from gpu_lab_twin.bootstrap import Container, build_container
from gpu_lab_twin.config.settings import Settings

T0 = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)

# Property tests check logic, not speed; a wall-clock deadline would make them load-dependent.
hypothesis_settings.register_profile("deterministic", deadline=None, derandomize=True)
hypothesis_settings.load_profile("deterministic")

# Default: isolated in-memory SQLite per test. Set GPU_TWIN_TEST_DATABASE_URL to an empty
# PostgreSQL database to run the same suite against the production dialect (schema is recreated per test).
TEST_DATABASE_URL = os.environ.get("GPU_TWIN_TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
_test_database = make_url(TEST_DATABASE_URL).database or ""
if not TEST_DATABASE_URL.startswith("sqlite") and not _test_database.endswith("_test"):
    # Every test drops and recreates the schema; refuse anything that is not a dedicated test database.
    raise pytest.UsageError(
        f"GPU_TWIN_TEST_DATABASE_URL must name a database ending in '_test', got {_test_database!r}"
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(database_url=TEST_DATABASE_URL, policy_version="test-policy-v1")


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock(T0)


@pytest.fixture
def container(settings: Settings, fake_clock: FakeClock) -> Iterator[Container]:
    built = build_container(settings, clock=fake_clock)
    Base.metadata.drop_all(built.engine)
    Base.metadata.create_all(built.engine)
    yield built
    built.engine.dispose()


@pytest.fixture
def client(container: Container) -> Iterator[TestClient]:
    with TestClient(create_app(container), raise_server_exceptions=False) as test_client:
        yield test_client
