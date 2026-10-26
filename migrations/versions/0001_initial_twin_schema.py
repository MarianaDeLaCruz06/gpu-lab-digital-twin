"""Initial twin schema: node aggregate, GPU devices, telemetry evidence, history, alerts, audit.

Mirrors docs/contracts/schema.sql for the tables Impl-1 uses. maintenance_locks arrives with Epic 3.

Revision ID: 0001
Revises:
Create Date: 2026-10-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_ENUMS = {
    "node_kind": ("WORKSTATION", "SERVER"),
    "node_state": ("UNKNOWN", "HEALTHY", "DEGRADED", "RECOVERING", "DRAINING", "MAINTENANCE", "OFFLINE"),
    "connectivity_status": ("UNKNOWN", "ONLINE", "SILENT", "CONNECTIVITY_UNSTABLE"),
    "driver_health": ("HEALTHY", "UNHEALTHY", "UNKNOWN"),
    "telemetry_disposition": ("APPLIED", "LATE_IGNORED", "BOOT_CHANGE_DETECTED"),
}


def _enum(name: str, is_pg: bool) -> sa.types.TypeEngine:
    if is_pg:
        return postgresql.ENUM(*_ENUMS[name], name=name, create_type=False)
    return sa.Enum(*_ENUMS[name], name=name)


def upgrade() -> None:
    is_pg = op.get_bind().dialect.name == "postgresql"
    if is_pg:
        for name, values in _ENUMS.items():
            postgresql.ENUM(*values, name=name).create(op.get_bind(), checkfirst=True)

    text_array = postgresql.ARRAY(sa.Text) if is_pg else sa.JSON()
    json_doc = postgresql.JSONB() if is_pg else sa.JSON()
    tstz = sa.DateTime(timezone=True)
    now = sa.text("CURRENT_TIMESTAMP")

    def pg_only(*checks: sa.CheckConstraint) -> list[sa.CheckConstraint]:
        return list(checks) if is_pg else []

    op.create_table(
        "nodes",
        sa.Column("node_id", sa.String(63), primary_key=True),
        sa.Column("kind", _enum("node_kind", is_pg), nullable=False),
        sa.Column("state", _enum("node_state", is_pg), nullable=False, server_default="UNKNOWN"),
        sa.Column("cordoned", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("connectivity", _enum("connectivity_status", is_pg), nullable=False, server_default="UNKNOWN"),
        sa.Column("revision", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("evidence_epoch", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("current_boot_session_id", sa.String(128)),
        sa.Column("heartbeat_interval_ms", sa.BigInteger, nullable=False),
        sa.Column("storage_capacity_gb", sa.Numeric(12, 3), nullable=False),
        sa.Column("last_accepted_event_at", tstz),
        sa.Column("last_accepted_receive_at", tstz),
        sa.Column(
            "active_reason_codes",
            text_array,
            nullable=False,
            server_default=sa.text("'{}'") if is_pg else sa.text("'[]'"),
        ),
        sa.Column("created_at", tstz, nullable=False, server_default=now),
        sa.Column("updated_at", tstz, nullable=False, server_default=now),
        sa.CheckConstraint("state = 'HEALTHY' OR cordoned = true", name="nodes_state_cordon_ck"),
        sa.CheckConstraint(
            "last_accepted_event_at IS NULL OR last_accepted_receive_at IS NOT NULL", name="nodes_last_times_ck"
        ),
        sa.CheckConstraint("revision >= 0", name="nodes_revision_ck"),
        sa.CheckConstraint("evidence_epoch >= 0", name="nodes_evidence_epoch_ck"),
        sa.CheckConstraint("heartbeat_interval_ms > 0", name="nodes_heartbeat_interval_ck"),
        sa.CheckConstraint("storage_capacity_gb > 0", name="nodes_storage_capacity_ck"),
        *pg_only(sa.CheckConstraint("node_id ~ '^[a-z0-9][a-z0-9-]{0,62}$'", name="nodes_node_id_ck")),
    )

    op.create_table(
        "gpu_devices",
        sa.Column("gpu_device_id", sa.String(128), primary_key=True),
        sa.Column("node_id", sa.String(63), sa.ForeignKey("nodes.node_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ordinal", sa.SmallInteger, nullable=False),
        sa.Column("vram_capacity_gb", sa.Numeric(8, 3), nullable=False),
        sa.Column("created_at", tstz, nullable=False, server_default=now),
        sa.UniqueConstraint("node_id", "ordinal"),
        sa.UniqueConstraint("node_id", "gpu_device_id"),
        sa.CheckConstraint("ordinal >= 0", name="gpu_devices_ordinal_ck"),
        sa.CheckConstraint("vram_capacity_gb IN (24, 48)", name="gpu_devices_vram_capacity_ck"),
    )

    op.create_table(
        "telemetry_snapshots",
        sa.Column("telemetry_id", sa.Uuid, primary_key=True),
        sa.Column("event_id", sa.Uuid, nullable=False, unique=True),
        sa.Column("node_id", sa.String(63), sa.ForeignKey("nodes.node_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("payload_hash", sa.CHAR(64), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("occurred_at", tstz, nullable=False),
        sa.Column("received_at", tstz, nullable=False),
        sa.Column("ingest_offset", sa.BigInteger, nullable=False, unique=True),
        sa.Column("source_sequence", sa.BigInteger),
        sa.Column("boot_session_id", sa.String(128), nullable=False),
        sa.Column("previous_boot_session_id", sa.String(128)),
        sa.Column("evidence_epoch", sa.BigInteger, nullable=False),
        sa.Column("state_loss", sa.Boolean, nullable=False),
        sa.Column("driver_health", _enum("driver_health", is_pg), nullable=False),
        sa.Column("storage_free_gb", sa.Numeric(12, 3), nullable=False),
        sa.Column("external_context", json_doc),
        sa.Column("disposition", _enum("telemetry_disposition", is_pg), nullable=False),
        sa.Column("is_current", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("explanation", json_doc, nullable=False),
        sa.Column("created_at", tstz, nullable=False, server_default=now),
        sa.CheckConstraint("schema_version = '1.0'", name="telemetry_schema_version_ck"),
        sa.CheckConstraint("ingest_offset >= 0", name="telemetry_ingest_offset_ck"),
        sa.CheckConstraint("source_sequence >= 0", name="telemetry_source_sequence_ck"),
        sa.CheckConstraint("evidence_epoch >= 0", name="telemetry_evidence_epoch_ck"),
        sa.CheckConstraint("storage_free_gb >= 0", name="telemetry_storage_free_ck"),
        *pg_only(
            sa.CheckConstraint("payload_hash ~ '^[0-9a-f]{64}$'", name="telemetry_payload_hash_ck"),
            sa.CheckConstraint(
                "external_context IS NULL OR external_context ->> 'source' = 'EXTERNAL_MOCK'",
                name="telemetry_external_source_ck",
            ),
        ),
    )
    op.create_index(
        "telemetry_one_current_per_node_uq",
        "telemetry_snapshots",
        ["node_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
        sqlite_where=sa.text("is_current"),
    )
    sequence_guard = "source_sequence IS NOT NULL AND disposition IN ('APPLIED','BOOT_CHANGE_DETECTED')"
    op.create_index(
        "telemetry_sequence_per_session_uq",
        "telemetry_snapshots",
        ["node_id", "boot_session_id", "source_sequence"],
        unique=True,
        postgresql_where=sa.text(sequence_guard),
        sqlite_where=sa.text(sequence_guard),
    )

    op.create_table(
        "telemetry_gpu_samples",
        sa.Column(
            "telemetry_id",
            sa.Uuid,
            sa.ForeignKey("telemetry_snapshots.telemetry_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "gpu_device_id",
            sa.String(128),
            sa.ForeignKey("gpu_devices.gpu_device_id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("temperature_c", sa.Numeric(7, 3), nullable=False),
        sa.Column("vram_occupied_gb", sa.Numeric(8, 3), nullable=False),
        sa.Column("created_at", tstz, nullable=False, server_default=now),
        sa.CheckConstraint("temperature_c >= 0", name="telemetry_gpu_temperature_ck"),
        sa.CheckConstraint("vram_occupied_gb >= 0", name="telemetry_gpu_vram_ck"),
    )

    op.create_table(
        "node_state_history",
        sa.Column("transition_id", sa.Uuid, primary_key=True),
        sa.Column("source_event_id", sa.Uuid, nullable=False),
        sa.Column("node_id", sa.String(63), sa.ForeignKey("nodes.node_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("prior_state", _enum("node_state", is_pg), nullable=False),
        sa.Column("result_state", _enum("node_state", is_pg), nullable=False),
        sa.Column("prior_cordoned", sa.Boolean, nullable=False),
        sa.Column("result_cordoned", sa.Boolean, nullable=False),
        sa.Column("node_revision", sa.BigInteger, nullable=False),
        sa.Column("rule_ids", text_array, nullable=False),
        sa.Column("evidence_ids", text_array, nullable=False),
        sa.Column("explanation", json_doc, nullable=False),
        sa.Column("occurred_at", tstz, nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("created_at", tstz, nullable=False, server_default=now),
        sa.UniqueConstraint("node_id", "node_revision"),
        sa.UniqueConstraint("source_event_id", "node_id", "result_state"),
        sa.CheckConstraint("node_revision > 0", name="history_node_revision_ck"),
        sa.CheckConstraint("schema_version = '1.0'", name="history_schema_version_ck"),
        *pg_only(
            sa.CheckConstraint("cardinality(rule_ids) > 0", name="history_rule_ids_ck"),
            sa.CheckConstraint("cardinality(evidence_ids) > 0", name="history_evidence_ids_ck"),
        ),
    )

    op.create_table(
        "alerts",
        sa.Column("alert_id", sa.Uuid, primary_key=True),
        sa.Column("node_id", sa.String(63), sa.ForeignKey("nodes.node_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reason_code", sa.String(128), nullable=False),
        sa.Column("opened_at", tstz, nullable=False),
        sa.Column("last_observed_at", tstz, nullable=False),
        sa.Column("closed_at", tstz),
        sa.Column("update_count", sa.BigInteger, nullable=False, server_default="1"),
        sa.Column("explanation", json_doc, nullable=False),
        sa.Column("created_at", tstz, nullable=False, server_default=now),
        sa.Column("updated_at", tstz, nullable=False, server_default=now),
        sa.CheckConstraint("closed_at IS NULL OR closed_at >= opened_at", name="alerts_close_order_ck"),
        sa.CheckConstraint("last_observed_at >= opened_at", name="alerts_observed_order_ck"),
        sa.CheckConstraint("update_count >= 1", name="alerts_update_count_ck"),
    )
    op.create_index(
        "alerts_one_open_per_reason_uq",
        "alerts",
        ["node_id", "reason_code"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
        sqlite_where=sa.text("closed_at IS NULL"),
    )

    op.create_table(
        "audit_events",
        sa.Column("audit_id", sa.Uuid, primary_key=True),
        sa.Column("event_id", sa.Uuid, nullable=False, unique=True),
        sa.Column("node_id", sa.String(63), sa.ForeignKey("nodes.node_id", ondelete="RESTRICT")),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("occurred_at", tstz, nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("rule_ids", text_array, nullable=False),
        sa.Column("evidence_ids", text_array, nullable=False),
        sa.Column("body", json_doc, nullable=False),
        sa.Column("created_at", tstz, nullable=False, server_default=now),
        sa.CheckConstraint("schema_version = '1.0'", name="audit_schema_version_ck"),
    )


def downgrade() -> None:
    for table in (
        "audit_events",
        "alerts",
        "node_state_history",
        "telemetry_gpu_samples",
        "telemetry_snapshots",
        "gpu_devices",
        "nodes",
    ):
        op.drop_table(table)
    if op.get_bind().dialect.name == "postgresql":
        for name in reversed(list(_ENUMS)):
            postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
