from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from gpu_lab_twin.adapters.db.models import Base
from gpu_lab_twin.config.settings import get_settings

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def migrated_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    url = f"sqlite+pysqlite:///{tmp_path / 'migrated.db'}"
    monkeypatch.setenv("GPU_TWIN_DATABASE_URL", url)
    get_settings.cache_clear()
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "head")
    yield url
    get_settings.cache_clear()


def test_migration_creates_exactly_the_mapped_tables_and_columns(migrated_url: str) -> None:
    inspector = inspect(create_engine(migrated_url))
    migrated = {table: {c["name"] for c in inspector.get_columns(table)} for table in inspector.get_table_names()}
    migrated.pop("alembic_version")

    mapped = {table.name: {c.name for c in table.columns} for table in Base.metadata.sorted_tables}

    assert migrated == mapped


def test_migration_creates_the_partial_unique_guards(migrated_url: str) -> None:
    inspector = inspect(create_engine(migrated_url))
    unique_indexes = {
        index["name"]
        for table in ("telemetry_snapshots", "alerts")
        for index in inspector.get_indexes(table)
        if index["unique"]
    }
    assert {
        "telemetry_one_current_per_node_uq",
        "telemetry_sequence_per_session_uq",
        "alerts_one_open_per_reason_uq",
    } <= unique_indexes
