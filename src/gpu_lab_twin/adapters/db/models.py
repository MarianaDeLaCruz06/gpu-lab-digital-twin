"""SQLAlchemy mapping of the complete canonical Solu-2 schema.

PostgreSQL-only checks (regex patterns, JSON operators, array cardinality) are attached
conditionally; the portable subset is what the SQLite test database enforces.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from gpu_lab_twin.adapters.db.types import JsonDocument, TextArray, UtcDateTime
from gpu_lab_twin.domain.fleet import NodeKind
from gpu_lab_twin.domain.node_state import ConnectivityStatus, DriverHealth, NodeState


class Base(DeclarativeBase):
    pass


node_kind_enum = SqlEnum(NodeKind, name="node_kind")
node_state_enum = SqlEnum(NodeState, name="node_state")
connectivity_enum = SqlEnum(ConnectivityStatus, name="connectivity_status")
driver_health_enum = SqlEnum(DriverHealth, name="driver_health")
disposition_enum = SqlEnum("APPLIED", "LATE_IGNORED", "BOOT_CHANGE_DETECTED", name="telemetry_disposition")


def _created_at() -> Mapped[datetime]:
    return mapped_column(UtcDateTime, nullable=False, server_default=func.current_timestamp())


class NodeRow(Base):
    __tablename__ = "nodes"
    __table_args__ = (
        CheckConstraint("state = 'HEALTHY' OR cordoned = true", name="nodes_state_cordon_ck"),
        CheckConstraint(
            "last_accepted_event_at IS NULL OR last_accepted_receive_at IS NOT NULL",
            name="nodes_last_times_ck",
        ),
        CheckConstraint("revision >= 0", name="nodes_revision_ck"),
        CheckConstraint("evidence_epoch >= 0", name="nodes_evidence_epoch_ck"),
        CheckConstraint("heartbeat_interval_ms > 0", name="nodes_heartbeat_interval_ck"),
        CheckConstraint("storage_capacity_gb > 0", name="nodes_storage_capacity_ck"),
        CheckConstraint("node_id ~ '^[a-z0-9][a-z0-9-]{0,62}$'", name="nodes_node_id_ck").ddl_if(dialect="postgresql"),
    )

    node_id: Mapped[str] = mapped_column(String(63), primary_key=True)
    kind: Mapped[NodeKind] = mapped_column(node_kind_enum, nullable=False)
    state: Mapped[NodeState] = mapped_column(node_state_enum, nullable=False, server_default=NodeState.UNKNOWN.value)
    cordoned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    connectivity: Mapped[ConnectivityStatus] = mapped_column(
        connectivity_enum, nullable=False, server_default=ConnectivityStatus.UNKNOWN.value
    )
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    evidence_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    current_boot_session_id: Mapped[str | None] = mapped_column(String(128))
    heartbeat_interval_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_capacity_gb: Mapped[float] = mapped_column(Numeric(12, 3, asdecimal=False), nullable=False)
    last_accepted_event_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    last_accepted_receive_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    active_reason_codes: Mapped[list[str]] = mapped_column(TextArray, nullable=False, default=list)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _created_at()


class GpuDeviceRow(Base):
    __tablename__ = "gpu_devices"
    __table_args__ = (
        UniqueConstraint("node_id", "ordinal"),
        UniqueConstraint("node_id", "gpu_device_id"),
        CheckConstraint("ordinal >= 0", name="gpu_devices_ordinal_ck"),
        CheckConstraint("vram_capacity_gb IN (24, 48)", name="gpu_devices_vram_capacity_ck"),
    )

    gpu_device_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.node_id", ondelete="RESTRICT"), nullable=False)
    ordinal: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    vram_capacity_gb: Mapped[float] = mapped_column(Numeric(8, 3, asdecimal=False), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class TelemetrySnapshotRow(Base):
    __tablename__ = "telemetry_snapshots"
    __table_args__ = (
        CheckConstraint("schema_version = '1.0'", name="telemetry_schema_version_ck"),
        CheckConstraint("ingest_offset >= 0", name="telemetry_ingest_offset_ck"),
        CheckConstraint("source_sequence >= 0", name="telemetry_source_sequence_ck"),
        CheckConstraint("evidence_epoch >= 0", name="telemetry_evidence_epoch_ck"),
        CheckConstraint("storage_free_gb >= 0", name="telemetry_storage_free_ck"),
        CheckConstraint("payload_hash ~ '^[0-9a-f]{64}$'", name="telemetry_payload_hash_ck").ddl_if(
            dialect="postgresql"
        ),
        CheckConstraint(
            "external_context IS NULL OR external_context ->> 'source' = 'EXTERNAL_MOCK'",
            name="telemetry_external_source_ck",
        ).ddl_if(dialect="postgresql"),
        Index(
            "telemetry_one_current_per_node_uq",
            "node_id",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current"),
        ),
        Index(
            "telemetry_sequence_per_session_uq",
            "node_id",
            "boot_session_id",
            "source_sequence",
            unique=True,
            postgresql_where=text("source_sequence IS NOT NULL AND disposition IN ('APPLIED','BOOT_CHANGE_DETECTED')"),
            sqlite_where=text("source_sequence IS NOT NULL AND disposition IN ('APPLIED','BOOT_CHANGE_DETECTED')"),
        ),
    )

    telemetry_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, unique=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.node_id", ondelete="RESTRICT"), nullable=False)
    payload_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    ingest_offset: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    source_sequence: Mapped[int | None] = mapped_column(BigInteger)
    boot_session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    previous_boot_session_id: Mapped[str | None] = mapped_column(String(128))
    evidence_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    state_loss: Mapped[bool] = mapped_column(Boolean, nullable=False)
    driver_health: Mapped[DriverHealth] = mapped_column(driver_health_enum, nullable=False)
    storage_free_gb: Mapped[float] = mapped_column(Numeric(12, 3, asdecimal=False), nullable=False)
    external_context: Mapped[dict | None] = mapped_column(JsonDocument)
    disposition: Mapped[str] = mapped_column(disposition_enum, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    explanation: Mapped[dict] = mapped_column(JsonDocument, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class TelemetryGpuSampleRow(Base):
    __tablename__ = "telemetry_gpu_samples"
    __table_args__ = (
        CheckConstraint("temperature_c >= 0", name="telemetry_gpu_temperature_ck"),
        CheckConstraint("vram_occupied_gb >= 0", name="telemetry_gpu_vram_ck"),
    )

    telemetry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("telemetry_snapshots.telemetry_id", ondelete="CASCADE"), primary_key=True
    )
    gpu_device_id: Mapped[str] = mapped_column(
        ForeignKey("gpu_devices.gpu_device_id", ondelete="RESTRICT"), primary_key=True
    )
    temperature_c: Mapped[float] = mapped_column(Numeric(7, 3, asdecimal=False), nullable=False)
    vram_occupied_gb: Mapped[float] = mapped_column(Numeric(8, 3, asdecimal=False), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class NodeStateHistoryRow(Base):
    __tablename__ = "node_state_history"
    __table_args__ = (
        UniqueConstraint("node_id", "node_revision"),
        UniqueConstraint("source_event_id", "node_id", "result_state"),
        CheckConstraint("node_revision > 0", name="history_node_revision_ck"),
        CheckConstraint("schema_version = '1.0'", name="history_schema_version_ck"),
        CheckConstraint("cardinality(rule_ids) > 0", name="history_rule_ids_ck").ddl_if(dialect="postgresql"),
        CheckConstraint("cardinality(evidence_ids) > 0", name="history_evidence_ids_ck").ddl_if(dialect="postgresql"),
    )

    transition_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    source_event_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.node_id", ondelete="RESTRICT"), nullable=False)
    prior_state: Mapped[NodeState] = mapped_column(node_state_enum, nullable=False)
    result_state: Mapped[NodeState] = mapped_column(node_state_enum, nullable=False)
    prior_cordoned: Mapped[bool] = mapped_column(Boolean, nullable=False)
    result_cordoned: Mapped[bool] = mapped_column(Boolean, nullable=False)
    node_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rule_ids: Mapped[list[str]] = mapped_column(TextArray, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(TextArray, nullable=False)
    explanation: Mapped[dict] = mapped_column(JsonDocument, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class MaintenanceLockRow(Base):
    __tablename__ = "maintenance_locks"
    __table_args__ = (
        CheckConstraint("expected_node_revision >= 0", name="maintenance_expected_revision_ck"),
        CheckConstraint(
            "(active AND released_at IS NULL) OR (NOT active AND released_at IS NOT NULL)",
            name="maintenance_release_ck",
        ),
        CheckConstraint("length(trim(reason)) > 0", name="maintenance_reason_ck"),
        CheckConstraint("length(trim(actor)) > 0", name="maintenance_actor_ck"),
        CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="maintenance_request_hash_ck").ddl_if(
            dialect="postgresql"
        ),
        Index(
            "maintenance_locks_one_active_uq",
            "node_id",
            unique=True,
            postgresql_where=text("active"),
            sqlite_where=text("active"),
        ),
    )

    lock_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, unique=True)
    request_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.node_id", ondelete="RESTRICT"), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    expected_node_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    released_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    release_request_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _created_at()


class AlertRow(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("closed_at IS NULL OR closed_at >= opened_at", name="alerts_close_order_ck"),
        CheckConstraint("last_observed_at >= opened_at", name="alerts_observed_order_ck"),
        CheckConstraint("update_count >= 1", name="alerts_update_count_ck"),
        Index(
            "alerts_one_open_per_reason_uq",
            "node_id",
            "reason_code",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
            sqlite_where=text("closed_at IS NULL"),
        ),
    )

    alert_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.node_id", ondelete="RESTRICT"), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(128), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    last_observed_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    update_count: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    explanation: Mapped[dict] = mapped_column(JsonDocument, nullable=False)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _created_at()


class AuditEventRow(Base):
    __tablename__ = "audit_events"
    __table_args__ = (CheckConstraint("schema_version = '1.0'", name="audit_schema_version_ck"),)

    audit_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, unique=True)
    node_id: Mapped[str | None] = mapped_column(ForeignKey("nodes.node_id", ondelete="RESTRICT"))
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_ids: Mapped[list[str]] = mapped_column(TextArray, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(TextArray, nullable=False)
    body: Mapped[dict] = mapped_column(JsonDocument, nullable=False)
    created_at: Mapped[datetime] = _created_at()
