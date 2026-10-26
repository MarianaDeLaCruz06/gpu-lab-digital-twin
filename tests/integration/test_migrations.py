from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, insert, inspect
from sqlalchemy.exc import IntegrityError

from gpu_lab_twin.adapters.db.models import Base, MaintenanceLockRow, NodeRow
from gpu_lab_twin.config.settings import get_settings
from gpu_lab_twin.domain.fleet import NodeKind

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
        for table in ("telemetry_snapshots", "maintenance_locks", "alerts")
        for index in inspector.get_indexes(table)
        if index["unique"]
    }
    assert {
        "telemetry_one_current_per_node_uq",
        "telemetry_sequence_per_session_uq",
        "maintenance_locks_one_active_uq",
        "alerts_one_open_per_reason_uq",
    } <= unique_indexes


def test_maintenance_locks_has_canonical_node_relationship_and_constraints(migrated_url: str) -> None:
    inspector = inspect(create_engine(migrated_url))
    foreign_keys = inspector.get_foreign_keys("maintenance_locks")
    checks = {check["name"] for check in inspector.get_check_constraints("maintenance_locks")}

    assert any(
        fk["constrained_columns"] == ["node_id"]
        and fk["referred_table"] == "nodes"
        and fk["referred_columns"] == ["node_id"]
        and fk["options"].get("ondelete") == "RESTRICT"
        for fk in foreign_keys
    )
    assert {
        "maintenance_expected_revision_ck",
        "maintenance_release_ck",
        "maintenance_reason_ck",
        "maintenance_actor_ck",
    } <= checks


def test_maintenance_lock_physical_invariants_reject_invalid_and_duplicate_rows(migrated_url: str) -> None:
    engine = create_engine(migrated_url)
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            insert(NodeRow).values(
                node_id="ws-lock-test",
                kind=NodeKind.WORKSTATION,
                heartbeat_interval_ms=10_000,
                storage_capacity_gb=500,
            )
        )
        connection.execute(
            insert(MaintenanceLockRow).values(
                lock_id=uuid.uuid4(),
                request_id=uuid.uuid4(),
                request_hash="a" * 64,
                node_id="ws-lock-test",
                reason="hardware inspection",
                actor="operator",
                acquired_at=now,
                expected_node_revision=0,
                active=True,
            )
        )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            insert(MaintenanceLockRow).values(
                lock_id=uuid.uuid4(),
                request_id=uuid.uuid4(),
                request_hash="b" * 64,
                node_id="ws-lock-test",
                reason="second active lock",
                actor="operator",
                acquired_at=now,
                expected_node_revision=0,
                active=True,
            )
        )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            insert(MaintenanceLockRow).values(
                lock_id=uuid.uuid4(),
                request_id=uuid.uuid4(),
                request_hash="c" * 64,
                node_id="ws-lock-test",
                reason="invalid release state",
                actor="operator",
                acquired_at=now,
                expected_node_revision=0,
                active=False,
                released_at=None,
            )
        )
