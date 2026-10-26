from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from gpu_lab_twin.adapters.db.models import (
    AlertRow,
    AuditEventRow,
    GpuDeviceRow,
    NodeRow,
    NodeStateHistoryRow,
    TelemetryGpuSampleRow,
    TelemetrySnapshotRow,
)
from gpu_lab_twin.domain.errors import DomainError, ErrorCode
from gpu_lab_twin.domain.fleet import FleetInventory
from gpu_lab_twin.domain.node import GpuReading, NodeSnapshot, NodeView
from gpu_lab_twin.ports.outbound.node_repository import (
    AuditRecord,
    HeartbeatCommit,
    ProjectionUpdate,
    RecordedHeartbeat,
    TransitionCommit,
    TransitionRecord,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0"
_ID_NAMESPACE = uuid5(NAMESPACE_URL, "urn:gpu-lab-digital-twin")


def _derived_id(*parts: object) -> UUID:
    """Deterministic row identity, so replaying the same inputs yields the same evidence IDs."""
    return uuid5(_ID_NAMESPACE, ":".join(str(part) for part in parts))


class SqlNodeRepository:
    """PostgreSQL/SQLite implementation of the NodeRepository port."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def seed_inventory(self, inventory: FleetInventory) -> int:
        with self._session_factory.begin() as session:
            existing = set(session.scalars(select(NodeRow.node_id)))
            added = 0
            for spec in inventory.nodes:
                if spec.node_id in existing:
                    continue
                session.add(
                    NodeRow(
                        node_id=spec.node_id,
                        kind=spec.kind,
                        heartbeat_interval_ms=spec.heartbeat_interval_ms,
                        storage_capacity_gb=spec.storage_capacity_gb,
                        active_reason_codes=[],
                    )
                )
                session.flush()
                session.add_all(
                    GpuDeviceRow(
                        gpu_device_id=gpu.gpu_device_id,
                        node_id=spec.node_id,
                        ordinal=gpu.ordinal,
                        vram_capacity_gb=gpu.vram_capacity_gb,
                    )
                    for gpu in spec.gpu_devices
                )
                added += 1
            return added

    def count_nodes(self) -> int:
        with self._session_factory() as session:
            return session.scalar(select(func.count()).select_from(NodeRow)) or 0

    def count_gpu_devices(self) -> int:
        with self._session_factory() as session:
            return session.scalar(select(func.count()).select_from(GpuDeviceRow)) or 0

    def get_node(self, node_id: str) -> NodeSnapshot | None:
        with self._session_factory() as session:
            row = session.get(NodeRow, node_id)
            if row is None:
                return None
            open_alerts = session.execute(
                select(AlertRow.reason_code, AlertRow.explanation).where(
                    AlertRow.node_id == node_id, AlertRow.closed_at.is_(None)
                )
            )
            open_alerts = list(open_alerts)
            evidence = {reason: tuple(explanation.get("evidenceIds", ())) for reason, explanation in open_alerts}
            observations = {reason: explanation.get("observedValues", {}) for reason, explanation in open_alerts}
            current_event = session.scalar(
                select(TelemetrySnapshotRow.event_id).where(
                    TelemetrySnapshotRow.node_id == node_id, TelemetrySnapshotRow.is_current
                )
            )
            return _snapshot(row, evidence, str(current_event) if current_event else None, observations)

    def find_heartbeat(self, event_id: UUID) -> RecordedHeartbeat | None:
        with self._session_factory() as session:
            found = session.execute(
                select(TelemetrySnapshotRow.node_id, TelemetrySnapshotRow.payload_hash, AuditEventRow.body)
                .join(AuditEventRow, AuditEventRow.event_id == TelemetrySnapshotRow.event_id)
                .where(TelemetrySnapshotRow.event_id == event_id)
            ).one_or_none()
            if found is None:
                return None
            return RecordedHeartbeat(
                node_id=found.node_id, payload_hash=found.payload_hash, response=found.body["response"]
            )

    def commit_heartbeat(self, commit: HeartbeatCommit) -> int:
        try:
            with self._session_factory.begin() as session:
                node_id = commit.projection.node_id
                revision = self._compare_and_set(session, commit.projection, commit.at)
                self._append_telemetry(session, commit)
                if commit.transition is not None:
                    self._append_transition(session, node_id, commit.transition, revision)
                self._close_alerts(session, node_id, commit.closed_alert_reasons, commit.at)
                for reason in commit.alert_reasons:
                    self._upsert_open_alert(session, node_id, reason, commit.at, commit.explanation)
                self._append_audit(session, node_id, commit.audit, commit.at)
                return revision
        except IntegrityError as exc:
            raise _integrity_error(exc, commit) from exc

    def commit_transition(self, commit: TransitionCommit) -> int:
        try:
            with self._session_factory.begin() as session:
                node_id = commit.projection.node_id
                revision = self._compare_and_set(session, commit.projection, commit.at)
                self._append_transition(session, node_id, commit.transition, revision)
                for reason in commit.alert_reasons:
                    self._upsert_open_alert(session, node_id, reason, commit.at, commit.explanation)
                self._append_audit(session, node_id, commit.audit, commit.at)
                return revision
        except IntegrityError as exc:
            logger.error("integrity error for transition %s: %s", commit.audit.event_id, exc.orig)
            raise DomainError(
                ErrorCode.ERR_INGRESS_UNAVAILABLE, "The evaluation was not committed; storage rejected the write."
            ) from exc

    def list_fleet(self) -> tuple[NodeView, ...]:
        with self._session_factory() as session:
            if session.get_bind().dialect.name == "postgresql":
                # One snapshot for all four reads, so no heartbeat can commit between them.
                session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
            nodes = session.scalars(select(NodeRow)).all()
            gpus = session.scalars(select(GpuDeviceRow).order_by(GpuDeviceRow.node_id, GpuDeviceRow.ordinal)).all()
            current = {
                row.node_id: row
                for row in session.scalars(select(TelemetrySnapshotRow).where(TelemetrySnapshotRow.is_current))
            }
            samples = {
                (row.telemetry_id, row.gpu_device_id): row
                for row in session.scalars(
                    select(TelemetryGpuSampleRow).where(
                        TelemetryGpuSampleRow.telemetry_id.in_([snap.telemetry_id for snap in current.values()])
                    )
                )
            }

        gpus_by_node: dict[str, list[GpuDeviceRow]] = defaultdict(list)
        for gpu in gpus:
            gpus_by_node[gpu.node_id].append(gpu)

        views = []
        for node in nodes:
            snapshot_row = current.get(node.node_id)
            readings = []
            for gpu in gpus_by_node[node.node_id]:
                sample = samples.get((snapshot_row.telemetry_id, gpu.gpu_device_id)) if snapshot_row else None
                readings.append(
                    GpuReading(
                        gpu_device_id=gpu.gpu_device_id,
                        vram_capacity_gb=gpu.vram_capacity_gb,
                        temperature_c=sample.temperature_c if sample else None,
                        vram_occupied_gb=sample.vram_occupied_gb if sample else None,
                    )
                )
            views.append(
                NodeView(
                    snapshot=_snapshot(node),
                    storage_capacity_gb=node.storage_capacity_gb,
                    storage_free_gb=snapshot_row.storage_free_gb if snapshot_row else None,
                    gpus=tuple(readings),
                )
            )
        return tuple(views)

    @staticmethod
    def _compare_and_set(session: Session, projection: ProjectionUpdate, at: datetime) -> int:
        revision = session.scalar(
            update(NodeRow)
            .where(NodeRow.node_id == projection.node_id, NodeRow.revision == projection.expected_revision)
            .values(
                state=projection.state,
                cordoned=projection.cordoned,
                connectivity=projection.connectivity,
                active_reason_codes=list(projection.active_reason_codes),
                current_boot_session_id=projection.current_boot_session_id,
                last_accepted_event_at=projection.last_accepted_event_at,
                last_accepted_receive_at=projection.last_accepted_receive_at,
                revision=NodeRow.revision + 1,
                updated_at=at,
            )
            .returning(NodeRow.revision)
        )
        if revision is None:
            actual = session.scalar(select(NodeRow.revision).where(NodeRow.node_id == projection.node_id))
            raise DomainError(
                ErrorCode.ERR_REVISION_CONFLICT,
                f"Expected revision {projection.expected_revision}; current revision is {actual}.",
                details={"expected": projection.expected_revision, "actual": actual},
            )
        return revision

    @staticmethod
    def _append_telemetry(session: Session, commit: HeartbeatCommit) -> None:
        payload = commit.payload
        node_id = commit.projection.node_id
        telemetry_id = _derived_id("telemetry", payload.event_id)
        next_offset = session.scalar(select(func.coalesce(func.max(TelemetrySnapshotRow.ingest_offset) + 1, 0)))

        session.execute(
            update(TelemetrySnapshotRow)
            .where(TelemetrySnapshotRow.node_id == node_id, TelemetrySnapshotRow.is_current)
            .values(is_current=False)
        )
        session.add(
            TelemetrySnapshotRow(
                telemetry_id=telemetry_id,
                event_id=payload.event_id,
                node_id=node_id,
                payload_hash=commit.payload_hash,
                schema_version=payload.schema_version,
                occurred_at=payload.occurred_at,
                received_at=commit.at,
                ingest_offset=next_offset,
                source_sequence=payload.source_sequence,
                boot_session_id=payload.boot_session_id,
                previous_boot_session_id=payload.previous_boot_session_id,
                evidence_epoch=commit.evidence_epoch,
                state_loss=payload.state_loss,
                driver_health=payload.driver_health,
                storage_free_gb=payload.storage_free_gb,
                external_context=dict(payload.external_context) if payload.external_context is not None else None,
                disposition="APPLIED",
                is_current=True,
                explanation=dict(commit.explanation),
            )
        )
        session.flush()
        session.add_all(
            TelemetryGpuSampleRow(
                telemetry_id=telemetry_id,
                gpu_device_id=sample.gpu_device_id,
                temperature_c=sample.temperature_c,
                vram_occupied_gb=sample.vram_occupied_gb,
            )
            for sample in payload.gpu_samples
        )

    @staticmethod
    def _append_transition(session: Session, node_id: str, transition: TransitionRecord, revision: int) -> None:
        session.add(
            NodeStateHistoryRow(
                transition_id=_derived_id("transition", transition.source_event_id, node_id),
                source_event_id=transition.source_event_id,
                node_id=node_id,
                prior_state=transition.prior_state,
                result_state=transition.result_state,
                prior_cordoned=transition.prior_cordoned,
                result_cordoned=transition.result_cordoned,
                node_revision=revision,
                rule_ids=list(transition.rule_ids),
                evidence_ids=list(transition.evidence_ids),
                explanation=dict(transition.explanation),
                occurred_at=transition.occurred_at,
                schema_version=SCHEMA_VERSION,
            )
        )

    @staticmethod
    def _close_alerts(session: Session, node_id: str, reasons: tuple[str, ...], at: datetime) -> None:
        if not reasons:
            return
        session.execute(
            update(AlertRow)
            .where(AlertRow.node_id == node_id, AlertRow.reason_code.in_(reasons), AlertRow.closed_at.is_(None))
            .values(closed_at=at, updated_at=at)
        )

    @staticmethod
    def _upsert_open_alert(session: Session, node_id: str, reason: str, at: datetime, explanation) -> None:
        """One open episode per (node, reason): the partial unique index arbitrates, not a prior SELECT."""
        dialect_insert = postgresql_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
        statement = dialect_insert(AlertRow).values(
            alert_id=_derived_id("alert", node_id, reason, at.isoformat()),
            node_id=node_id,
            reason_code=reason,
            opened_at=at,
            last_observed_at=at,
            update_count=1,
            explanation=dict(explanation),
            updated_at=at,
        )
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[AlertRow.node_id, AlertRow.reason_code],
                index_where=AlertRow.closed_at.is_(None),
                set_={
                    "last_observed_at": at,
                    "update_count": AlertRow.update_count + 1,
                    "explanation": statement.excluded.explanation,
                    "updated_at": at,
                },
            )
        )

    @staticmethod
    def _append_audit(session: Session, node_id: str, audit: AuditRecord, at: datetime) -> None:
        session.add(
            AuditEventRow(
                audit_id=_derived_id("audit", audit.event_id),
                event_id=audit.event_id,
                node_id=node_id,
                event_type=audit.event_type,
                occurred_at=at,
                schema_version=SCHEMA_VERSION,
                rule_ids=list(audit.rule_ids),
                evidence_ids=list(audit.evidence_ids),
                body=dict(audit.body),
            )
        )


def _snapshot(
    row: NodeRow,
    reason_evidence: dict[str, tuple[str, ...]] | None = None,
    current_heartbeat_event_id: str | None = None,
    reason_observations: dict[str, dict] | None = None,
) -> NodeSnapshot:
    return NodeSnapshot(
        node_id=row.node_id,
        kind=row.kind,
        state=row.state,
        cordoned=row.cordoned,
        connectivity=row.connectivity,
        revision=row.revision,
        evidence_epoch=row.evidence_epoch,
        current_boot_session_id=row.current_boot_session_id,
        heartbeat_interval_ms=row.heartbeat_interval_ms,
        last_accepted_event_at=row.last_accepted_event_at,
        last_accepted_receive_at=row.last_accepted_receive_at,
        active_reason_codes=tuple(row.active_reason_codes or ()),
        reason_evidence=reason_evidence or {},
        current_heartbeat_event_id=current_heartbeat_event_id,
        reason_observations=reason_observations or {},
    )


# Unique-violation markers: PostgreSQL reports the constraint name, SQLite the table.column list.
_SEQUENCE_CONSTRAINTS = ("telemetry_sequence_per_session_uq", "telemetry_snapshots.source_sequence")
_EVENT_ID_CONSTRAINTS = (
    "telemetry_snapshots_event_id_key",
    "audit_events_event_id_key",
    "telemetry_snapshots.event_id",
    "audit_events.event_id",
)


def _violates(message: str, markers: tuple[str, ...]) -> bool:
    return any(marker in message for marker in markers)


def _integrity_error(exc: IntegrityError, commit: HeartbeatCommit) -> DomainError:
    message = str(exc.orig)
    if _violates(message, _SEQUENCE_CONSTRAINTS):
        return DomainError(
            ErrorCode.ERR_ORDER_AMBIGUOUS,
            f"sourceSequence {commit.payload.source_sequence} was already applied for boot session "
            f"{commit.payload.boot_session_id}; provide a higher sourceSequence.",
            details={"sourceSequence": commit.payload.source_sequence, "bootSessionId": commit.payload.boot_session_id},
        )
    if _violates(message, _EVENT_ID_CONSTRAINTS):
        return DomainError(
            ErrorCode.ERR_IDEMPOTENCY_CONFLICT,
            f"{commit.payload.event_id} was already used.",
            details={"eventId": str(commit.payload.event_id)},
        )
    logger.error("unmapped integrity error for event %s: %s", commit.payload.event_id, message)
    return DomainError(ErrorCode.ERR_INGRESS_UNAVAILABLE, "The event was not accepted; storage rejected the write.")
