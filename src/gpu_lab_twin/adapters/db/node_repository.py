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
    MaintenanceLockRow,
    NodeRow,
    NodeStateHistoryRow,
    TelemetryGpuSampleRow,
    TelemetrySnapshotRow,
)
from gpu_lab_twin.domain.errors import DomainError, ErrorCode
from gpu_lab_twin.domain.fleet import FleetInventory
from gpu_lab_twin.domain.maintenance import MaintenanceResult, MaintenanceWindow, WorkloadSnapshot, maintenance_state
from gpu_lab_twin.domain.node import GpuReading, NodeSnapshot, NodeView
from gpu_lab_twin.domain.node_state import NodeState
from gpu_lab_twin.ports.outbound.node_repository import (
    AuditRecord,
    ConnectivityObservationCommit,
    HeartbeatCommit,
    IgnoredHeartbeatCommit,
    ProjectionUpdate,
    RecordedConnectivityObservation,
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
            current = session.execute(
                select(TelemetrySnapshotRow.event_id, TelemetrySnapshotRow.source_sequence).where(
                    TelemetrySnapshotRow.node_id == node_id, TelemetrySnapshotRow.is_current
                )
            ).one_or_none()
            return _snapshot(
                row,
                evidence,
                str(current.event_id) if current else None,
                observations,
                current.source_sequence if current else None,
            )

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

    def find_connectivity_observation(self, event_id: UUID) -> RecordedConnectivityObservation | None:
        with self._session_factory() as session:
            found = session.execute(
                select(AuditEventRow.node_id, AuditEventRow.event_type, AuditEventRow.body).where(
                    AuditEventRow.event_id == event_id
                )
            ).one_or_none()
            if found is None:
                return None
            return RecordedConnectivityObservation(
                node_id=found.node_id or "",
                observation_hash=(
                    found.body.get("observationHash", "__event_type_conflict__")
                    if found.event_type == "ConnectivityObserved"
                    else "__event_type_conflict__"
                ),
                response=found.body.get("response", {}),
            )

    def has_boot_session(self, node_id: str, boot_session_id: str) -> bool:
        with self._session_factory() as session:
            count = session.scalar(
                select(func.count())
                .select_from(TelemetrySnapshotRow)
                .where(
                    TelemetrySnapshotRow.node_id == node_id,
                    TelemetrySnapshotRow.boot_session_id == boot_session_id,
                )
            )
            return bool(count)

    def commit_heartbeat(self, commit: HeartbeatCommit) -> int:
        result = self.commit_heartbeat_batch((commit,))
        revision = result[0]
        assert revision is not None
        return revision

    def commit_heartbeat_batch(
        self, commits: tuple[HeartbeatCommit | IgnoredHeartbeatCommit, ...]
    ) -> tuple[int | None, ...]:
        if not commits:
            return ()
        try:
            with self._session_factory.begin() as session:
                base_offset = session.scalar(select(func.coalesce(func.max(TelemetrySnapshotRow.ingest_offset) + 1, 0)))
                revisions: list[int | None] = []
                # last applied commit index per node for is_current
                last_applied_for_node: dict[str, int] = {}
                for idx, commit in enumerate(commits):
                    if isinstance(commit, HeartbeatCommit):
                        last_applied_for_node[commit.projection.node_id] = idx
                # clear is_current for nodes that will receive a new current snapshot in this batch
                for node_id in last_applied_for_node:
                    session.execute(
                        update(TelemetrySnapshotRow)
                        .where(TelemetrySnapshotRow.node_id == node_id, TelemetrySnapshotRow.is_current)
                        .values(is_current=False)
                    )
                for idx, commit in enumerate(commits):
                    offset = base_offset + idx
                    if isinstance(commit, HeartbeatCommit):
                        node_id = commit.projection.node_id
                        revision = self._compare_and_set(session, commit.projection, commit.at)
                        is_current = last_applied_for_node.get(node_id) == idx
                        self._append_telemetry(
                            session, commit, ingest_offset=offset, clear_current=False, is_current=is_current
                        )
                        if commit.transition is not None:
                            self._append_transition(session, node_id, commit.transition, revision)
                        self._close_alerts(session, node_id, commit.closed_alert_reasons, commit.at)
                        for reason in commit.alert_reasons:
                            self._upsert_open_alert(session, node_id, reason, commit.at, commit.explanation)
                        self._append_audit(session, node_id, commit.audit, commit.at)
                        revisions.append(revision)
                    else:
                        self._append_telemetry(
                            session,
                            commit,
                            disposition="LATE_IGNORED",
                            is_current=False,
                            ingest_offset=offset,
                            clear_current=False,
                        )
                        self._append_audit(
                            session,
                            commit.node_id,
                            AuditRecord(
                                event_id=commit.payload.event_id,
                                event_type="HeartbeatLateIgnored",
                                rule_ids=tuple(commit.explanation["ruleIds"]),
                                evidence_ids=tuple(commit.explanation["evidenceIds"]),
                                body={"response": dict(commit.result), "transitioned": False},
                            ),
                            commit.at,
                        )
                        revisions.append(None)
                return tuple(revisions)
        except IntegrityError as exc:
            # find the first applied commit for error mapping; best effort
            first = next((c for c in commits if isinstance(c, HeartbeatCommit)), commits[0])
            raise _integrity_error(exc, first) from exc

    def commit_ignored_heartbeat(self, commit: IgnoredHeartbeatCommit) -> None:
        self.commit_heartbeat_batch((commit,))

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

    def commit_connectivity_observation(self, commit: ConnectivityObservationCommit) -> None:
        try:
            with self._session_factory.begin() as session:
                self._upsert_open_alert(
                    session,
                    commit.node_id,
                    commit.reason_code,
                    commit.accepted_at,
                    commit.explanation,
                )
                self._append_audit(
                    session,
                    commit.node_id,
                    AuditRecord(
                        event_id=commit.event_id,
                        event_type="ConnectivityObserved",
                        rule_ids=(commit.reason_code,),
                        evidence_ids=(str(commit.event_id),),
                        body={
                            "observationHash": commit.observation_hash,
                            "observation": commit.observation,
                            "observedAt": commit.observed_at.isoformat(),
                            "response": dict(commit.response),
                            "transitioned": False,
                        },
                    ),
                    commit.accepted_at,
                )
        except IntegrityError as exc:
            message = str(exc.orig)
            if _violates(message, _EVENT_ID_CONSTRAINTS):
                raise DomainError(
                    ErrorCode.ERR_IDEMPOTENCY_CONFLICT,
                    f"{commit.event_id} was already used.",
                    details={"eventId": str(commit.event_id)},
                ) from exc
            logger.error("integrity error for connectivity observation %s: %s", commit.event_id, message)
            raise DomainError(
                ErrorCode.ERR_INGRESS_UNAVAILABLE,
                "The connectivity observation was not accepted; storage rejected the write.",
            ) from exc

    def schedule_maintenance(self, node_id: str, window: MaintenanceWindow, at: datetime) -> MaintenanceResult:
        request_hash = window.canonical_hash(node_id)
        with self._session_factory.begin() as session:
            existing = session.scalar(
                select(MaintenanceLockRow).where(MaintenanceLockRow.request_id == window.request_id)
            )
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise DomainError(
                        ErrorCode.ERR_IDEMPOTENCY_CONFLICT,
                        f"{window.request_id} was already used for a different maintenance request.",
                    )
                return _maintenance_result(window, existing, session.get(NodeRow, node_id), "DUPLICATE", None)
            active = session.scalar(
                select(MaintenanceLockRow).where(
                    MaintenanceLockRow.node_id == node_id, MaintenanceLockRow.active.is_(True)
                )
            )
            if active is not None:
                raise DomainError(
                    ErrorCode.ERR_MAINTENANCE_CONFLICT,
                    f"Node {node_id} already has active maintenance lock {active.lock_id}.",
                    details={"lockId": str(active.lock_id)},
                )
            node = session.get(NodeRow, node_id)
            if node is None:
                raise DomainError(ErrorCode.ERR_UNKNOWN_NODE, f"Node {node_id} is not configured.")
            if node.revision != window.expected_node_revision:
                raise DomainError(
                    ErrorCode.ERR_REVISION_CONFLICT,
                    f"Expected revision {window.expected_node_revision}; current revision is {node.revision}.",
                    details={"expected": window.expected_node_revision, "actual": node.revision},
                )
            prior_state, prior_cordoned = node.state, node.cordoned
            lock = MaintenanceLockRow(
                lock_id=_derived_id("maintenance-lock", window.request_id),
                request_id=window.request_id,
                request_hash=request_hash,
                node_id=node_id,
                reason=window.reason.strip(),
                actor=window.actor.strip(),
                acquired_at=window.starts_at,
                expected_node_revision=window.expected_node_revision,
                active=True,
                updated_at=at,
            )
            session.add(lock)
            node.state = NodeState.DRAINING
            node.cordoned = True
            node.active_reason_codes = sorted(set(node.active_reason_codes or ()) | {"DRAIN_STATUS_UNKNOWN"})
            node.revision += 1
            node.updated_at = at
            result = _maintenance_result(window, lock, node, "SCHEDULED", None)
            session.add(
                NodeStateHistoryRow(
                    transition_id=_derived_id("transition", window.event_id, node_id),
                    source_event_id=window.event_id,
                    node_id=node_id,
                    prior_state=prior_state,
                    result_state=node.state,
                    prior_cordoned=prior_cordoned,
                    result_cordoned=True,
                    node_revision=node.revision,
                    rule_ids=["MAINTENANCE_DRAIN_ACTIVE"],
                    evidence_ids=[str(window.event_id), str(lock.lock_id)],
                    explanation=result.explanation,
                    occurred_at=at,
                    schema_version=SCHEMA_VERSION,
                )
            )
            self._append_audit(
                session,
                node_id,
                AuditRecord(
                    event_id=window.event_id,
                    event_type="MaintenanceDrainScheduled",
                    rule_ids=("MAINTENANCE_DRAIN_ACTIVE",),
                    evidence_ids=(str(window.event_id), str(lock.lock_id)),
                    body={"requestId": str(window.request_id), "response": result.as_document()},
                ),
                at,
            )
            return result

    def apply_workload_snapshot(self, snapshot: WorkloadSnapshot, at: datetime) -> MaintenanceResult:
        with self._session_factory.begin() as session:
            duplicate = session.scalar(select(AuditEventRow).where(AuditEventRow.event_id == snapshot.event_id))
            lock = session.scalar(
                select(MaintenanceLockRow).where(
                    MaintenanceLockRow.node_id == snapshot.node_id, MaintenanceLockRow.active.is_(True)
                )
            )
            if lock is None:
                raise DomainError(
                    ErrorCode.ERR_EVIDENCE_NOT_FOUND, f"Node {snapshot.node_id} has no active maintenance lock."
                )
            node = session.get(NodeRow, snapshot.node_id)
            if duplicate is not None:
                return _snapshot_result(snapshot, lock, node, "DUPLICATE")
            prior_revisions = [
                row.body.get("sourceRevision", -1)
                for row in session.scalars(
                    select(AuditEventRow).where(
                        AuditEventRow.node_id == snapshot.node_id,
                        AuditEventRow.event_type == "WorkloadSnapshotReceived",
                    )
                )
            ]
            if prior_revisions and snapshot.source_revision <= max(prior_revisions):
                raise DomainError(
                    ErrorCode.ERR_LATE_EVENT,
                    f"Workload sourceRevision {snapshot.source_revision} is not newer than {max(prior_revisions)}.",
                )
            state = maintenance_state(lock_acquired_at=lock.acquired_at, snapshot=snapshot)
            if state is not NodeState.MAINTENANCE and snapshot.active_workload_count == 0:
                raise DomainError(
                    ErrorCode.ERR_EVIDENCE_NOT_FOUND,
                    "A workload snapshot observed before lock acquisition cannot complete the drain.",
                )
            prior_state, prior_cordoned = node.state, node.cordoned
            node.state = state
            node.cordoned = True
            reasons = set(node.active_reason_codes or ())
            if state is NodeState.MAINTENANCE:
                reasons.discard("DRAIN_STATUS_UNKNOWN")
            node.active_reason_codes = sorted(reasons)
            node.revision += 1
            node.updated_at = at
            result = _snapshot_result(snapshot, lock, node, "APPLIED")
            if (prior_state, prior_cordoned) != (node.state, node.cordoned):
                session.add(
                    NodeStateHistoryRow(
                        transition_id=_derived_id("transition", snapshot.event_id, snapshot.node_id),
                        source_event_id=snapshot.event_id,
                        node_id=snapshot.node_id,
                        prior_state=prior_state,
                        result_state=node.state,
                        prior_cordoned=prior_cordoned,
                        result_cordoned=True,
                        node_revision=node.revision,
                        rule_ids=["MAINTENANCE_FRESH_ZERO"],
                        evidence_ids=[str(snapshot.event_id), str(lock.lock_id)],
                        explanation=result.explanation,
                        occurred_at=at,
                        schema_version=SCHEMA_VERSION,
                    )
                )
            self._append_audit(
                session,
                snapshot.node_id,
                AuditRecord(
                    event_id=snapshot.event_id,
                    event_type="WorkloadSnapshotReceived",
                    rule_ids=(
                        "MAINTENANCE_FRESH_ZERO" if state is NodeState.MAINTENANCE else "MAINTENANCE_DRAIN_ACTIVE",
                    ),
                    evidence_ids=(str(snapshot.event_id), str(lock.lock_id)),
                    body={"sourceRevision": snapshot.source_revision, "response": result.as_document()},
                ),
                at,
            )
            return result

    def count_active_maintenance_locks(self, node_id: str) -> int:
        with self._session_factory() as session:
            return (
                session.scalar(
                    select(func.count())
                    .select_from(MaintenanceLockRow)
                    .where(MaintenanceLockRow.node_id == node_id, MaintenanceLockRow.active.is_(True))
                )
                or 0
            )

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
                **({"evidence_epoch": projection.evidence_epoch} if projection.evidence_epoch is not None else {}),
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
    def _append_telemetry(
        session: Session,
        commit: HeartbeatCommit | IgnoredHeartbeatCommit,
        *,
        disposition: str | None = None,
        is_current: bool = True,
        ingest_offset: int | None = None,
        clear_current: bool = True,
    ) -> None:
        payload = commit.payload
        node_id = commit.projection.node_id if isinstance(commit, HeartbeatCommit) else commit.node_id
        telemetry_id = _derived_id("telemetry", payload.event_id)
        next_offset = (
            ingest_offset
            if ingest_offset is not None
            else session.scalar(select(func.coalesce(func.max(TelemetrySnapshotRow.ingest_offset) + 1, 0)))
        )

        if is_current and clear_current:
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
                disposition=disposition or commit.disposition,
                is_current=is_current,
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


def _maintenance_explanation(
    *, node: NodeRow, evidence_ids: list[str], workload_count: int | None, state: NodeState
) -> dict:
    return {
        "ruleIds": ["MAINTENANCE_FRESH_ZERO" if state is NodeState.MAINTENANCE else "MAINTENANCE_DRAIN_ACTIVE"],
        "observedValues": {"activeWorkloadCount": workload_count},
        "thresholds": {"completion": {"operator": "equals", "value": 0}},
        "expectedState": state.value,
        "evidenceIds": evidence_ids,
        "policyVersion": "ad-7-v1",
        "priorState": node.state.value,
        "resultState": state.value,
        "summary": (
            f"{node.node_id} entered MAINTENANCE after a fresh zero-workload snapshot."
            if state is NodeState.MAINTENANCE
            else f"{node.node_id} is DRAINING while workload evidence is unknown or positive."
        ),
    }


def _maintenance_result(
    window: MaintenanceWindow,
    lock: MaintenanceLockRow,
    node: NodeRow,
    outcome: str,
    workload_count: int | None,
) -> MaintenanceResult:
    return MaintenanceResult(
        event_id=window.event_id,
        request_id=window.request_id,
        node_id=node.node_id,
        outcome=outcome,
        lock_id=lock.lock_id,
        node_revision=node.revision,
        state=node.state,
        cordoned=True,
        active_workload_count=workload_count,
        active_workload_ids=(),
        workload_observed_at=None,
        explanation=_maintenance_explanation(
            node=node,
            evidence_ids=[str(window.event_id), str(lock.lock_id)],
            workload_count=workload_count,
            state=node.state,
        ),
    )


def _snapshot_result(
    snapshot: WorkloadSnapshot, lock: MaintenanceLockRow, node: NodeRow, outcome: str
) -> MaintenanceResult:
    return MaintenanceResult(
        event_id=snapshot.event_id,
        request_id=lock.request_id,
        node_id=node.node_id,
        outcome=outcome,
        lock_id=lock.lock_id,
        node_revision=node.revision,
        state=node.state,
        cordoned=True,
        active_workload_count=snapshot.active_workload_count,
        active_workload_ids=snapshot.active_workload_ids,
        workload_observed_at=snapshot.observed_at,
        explanation=_maintenance_explanation(
            node=node,
            evidence_ids=[str(snapshot.event_id), str(lock.lock_id)],
            workload_count=snapshot.active_workload_count,
            state=node.state,
        ),
    )


def _snapshot(
    row: NodeRow,
    reason_evidence: dict[str, tuple[str, ...]] | None = None,
    current_heartbeat_event_id: str | None = None,
    reason_observations: dict[str, dict] | None = None,
    current_source_sequence: int | None = None,
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
        current_source_sequence=current_source_sequence,
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


def _integrity_error(exc: IntegrityError, commit: HeartbeatCommit | IgnoredHeartbeatCommit) -> DomainError:
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
