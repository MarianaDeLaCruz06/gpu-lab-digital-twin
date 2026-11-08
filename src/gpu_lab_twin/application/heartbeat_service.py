from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from gpu_lab_twin.domain.errors import DomainError, ErrorCode
from gpu_lab_twin.domain.explanation import Explanation, explain_heartbeat_decision
from gpu_lab_twin.domain.fleet import FleetInventory
from gpu_lab_twin.domain.heartbeat import HeartbeatPayload
from gpu_lab_twin.domain.heartbeat_policy import check_boot_succession, reasons_from, validate_heartbeat
from gpu_lab_twin.domain.node import NodeSnapshot
from gpu_lab_twin.domain.node_state import ConnectivityStatus, Decision, NodeFacts, NodeState, ReasonCode, evaluate
from gpu_lab_twin.domain.telemetry_downsampling import TelemetryDownsampler
from gpu_lab_twin.ports.inbound.heartbeat import HeartbeatResult
from gpu_lab_twin.ports.outbound.clock import Clock
from gpu_lab_twin.ports.outbound.node_repository import (
    AuditRecord,
    HeartbeatCommit,
    IgnoredHeartbeatCommit,
    NodeRepository,
    ProjectionUpdate,
    TransitionRecord,
)

if TYPE_CHECKING:
    from gpu_lab_twin.application.heartbeat_batch_writer import DurableHeartbeatBatchWriter, HeartbeatCommand


@dataclass(slots=True)
class _PreparedHeartbeat:
    cmd: HeartbeatCommand
    result: HeartbeatResult
    commit: HeartbeatCommit | IgnoredHeartbeatCommit | None
    observe_payload: HeartbeatPayload | None = None


class HeartbeatService:
    """Implements HeartbeatPort.

    ``write_lock`` is the process-wide serialization point (AD-1). In batched mode, the HTTP path
    enqueues and waits (ack-after-commit); the sequencer thread holds ``write_lock`` while preparing
    and committing batches to preserve ordering and shared-mutation safety with liveness/maintenance.
    """

    def __init__(
        self,
        *,
        inventory: FleetInventory,
        nodes: NodeRepository,
        clock: Clock,
        policy_version: str,
        write_lock: threading.Lock,
        downsampler: TelemetryDownsampler | None = None,
        batch_writer: DurableHeartbeatBatchWriter | None = None,
    ) -> None:
        self._inventory = inventory
        self._nodes = nodes
        self._clock = clock
        self._policy_version = policy_version
        self._write_lock = write_lock
        self._downsampler = downsampler
        self._batch_writer = batch_writer

    def attach_batch_writer(self, writer: DurableHeartbeatBatchWriter) -> None:
        self._batch_writer = writer

    def submit_heartbeat(self, node_id: str, payload: HeartbeatPayload):
        writer = self._batch_writer
        if writer is not None and getattr(writer, "_started", False):
            return writer.submit(node_id, payload)
        from concurrent.futures import Future

        f: Future[HeartbeatResult] = Future()
        try:
            f.set_result(self._ingest_sync(node_id, payload))
        except Exception as exc:
            f.set_exception(exc)
        return f

    def ingest_heartbeat(self, node_id: str, payload: HeartbeatPayload) -> HeartbeatResult:
        return self.submit_heartbeat(node_id, payload).result()

    def _ingest_sync(self, node_id: str, payload: HeartbeatPayload) -> HeartbeatResult:
        with self._write_lock:
            prepared = self._prepare(node_id, payload)
            if prepared.commit is not None:
                self._commit_prepared((prepared,))
            self._observe_prepared((prepared,))
            return prepared.result

    def process_commands(self, commands: Sequence[HeartbeatCommand]) -> None:
        """Prepare and durably commit commands in FIFO order. Caller (batch writer) holds ``write_lock``."""
        if not commands:
            return
        pending: list[_PreparedHeartbeat] = []
        pending_nodes: set[str] = set()
        for cmd in commands:
            # Keep prepare reads consistent with any pending uncommitted state for the same node.
            if cmd.node_id in pending_nodes:
                self._flush_prepared(pending)
                pending = []
                pending_nodes = set()
            try:
                prepared = self._prepare(cmd.node_id, cmd.payload)
                prepared.cmd = cmd
            except Exception as exc:
                if pending:
                    self._flush_prepared(pending)
                    pending = []
                    pending_nodes = set()
                if not cmd.future.done():
                    cmd.future.set_exception(exc)
                continue

            commit_node = _commit_node(prepared.commit)
            pending.append(prepared)
            if commit_node is not None:
                pending_nodes.add(commit_node)
        if pending:
            self._flush_prepared(pending)

    def _flush_prepared(self, prepared: Sequence[_PreparedHeartbeat]) -> None:
        durable = [p for p in prepared if p.commit is not None]
        if durable:
            commits = tuple(p.commit for p in durable if p.commit is not None)
            revisions = self._nodes.commit_heartbeat_batch(commits)
            for rev, p in zip(revisions, durable, strict=True):
                if isinstance(p.commit, HeartbeatCommit) and rev is not None and rev != p.result.node_revision:
                    # Repository is authoritative for CAS revision; keep returned result consistent.
                    p.result = HeartbeatResult(
                        event_id=p.result.event_id,
                        node_id=p.result.node_id,
                        outcome=p.result.outcome,
                        node_revision=rev,
                        state=p.result.state,
                        cordoned=p.result.cordoned,
                        connectivity_status=p.result.connectivity_status,
                        accepted_at=p.result.accepted_at,
                        explanation=p.result.explanation,
                    )
        for p in prepared:
            if not p.cmd.future.done():
                p.cmd.future.set_result(p.result)
        self._observe_prepared(prepared)

    def _commit_prepared(self, prepared: Sequence[_PreparedHeartbeat]) -> None:
        commits = tuple(p.commit for p in prepared if p.commit is not None)
        if commits:
            self._nodes.commit_heartbeat_batch(commits)

    def _observe_prepared(self, prepared: Sequence[_PreparedHeartbeat]) -> None:
        if self._downsampler is None:
            return
        for p in prepared:
            if p.observe_payload is not None and p.result.outcome in {"APPLIED", "BOOT_CHANGE_DETECTED"}:
                self._downsampler.observe(p.result.node_id, p.observe_payload)

    def _prepare(self, node_id: str, payload: HeartbeatPayload) -> _PreparedHeartbeat:
        spec = self._inventory.node(node_id)
        if spec is None:
            raise _unknown_node(node_id)
        payload_hash = payload.canonical_hash(node_id)

        # Read time in commit/receive order; batched mode reads per command in FIFO order.
        at = self._clock.now()
        validate_heartbeat(spec, payload, at)

        recorded = self._nodes.find_heartbeat(payload.event_id)
        if recorded is not None:
            if recorded.payload_hash != payload_hash:
                raise DomainError(
                    ErrorCode.ERR_IDEMPOTENCY_CONFLICT,
                    f"{payload.event_id} was already used for a different payload (node {recorded.node_id}).",
                    details={"eventId": str(payload.event_id), "recordedNodeId": recorded.node_id},
                )
            result = HeartbeatResult.from_document(recorded.response, outcome="DUPLICATE")
            return _PreparedHeartbeat(cmd=_dummy_cmd(node_id, payload), result=result, commit=None)

        node = self._nodes.get_node(node_id)
        if node is None:
            raise _unknown_node(node_id)
        if node.last_accepted_receive_at is not None and at < node.last_accepted_receive_at:
            raise DomainError(
                ErrorCode.ERR_CLOCK_ORDER,
                f"Time {at.isoformat()} must be later than {node.last_accepted_receive_at.isoformat()}.",
                details={"supplied": at.isoformat(), "lastAccepted": node.last_accepted_receive_at.isoformat()},
            )
        known_prior_boot = (
            node.current_boot_session_id is not None
            and payload.boot_session_id != node.current_boot_session_id
            and self._nodes.has_boot_session(node_id, payload.boot_session_id)
        )
        if known_prior_boot or _is_late_current_epoch(node, payload):
            late_result, late_commit = self._late(node, payload, payload_hash, at)
            return _PreparedHeartbeat(cmd=_dummy_cmd(node_id, payload), result=late_result, commit=late_commit)

        boot_change = check_boot_succession(node, payload)

        known_reasons = {reason.value for reason in ReasonCode}
        retained_status_reasons = tuple(code for code in node.active_reason_codes if code not in known_reasons)
        prior_reasons = frozenset(ReasonCode(code) for code in node.active_reason_codes if code in known_reasons)
        current_reasons = reasons_from(payload)
        closed: tuple[ReasonCode, ...] = ()
        if boot_change:
            closed = tuple(prior_reasons)
            prior_reasons = frozenset()
            current_reasons |= {ReasonCode.RECOVERY_PENDING}
        elif ReasonCode.SILENT in prior_reasons:
            prior_reasons -= {ReasonCode.SILENT}
            current_reasons |= {ReasonCode.RECOVERY_PENDING}
            closed = (ReasonCode.SILENT,)
        retained = prior_reasons - current_reasons
        maintenance_active = node.state in {NodeState.DRAINING, NodeState.MAINTENANCE}
        decision = evaluate(
            NodeFacts(
                has_current_heartbeat=True,
                reasons=prior_reasons | current_reasons,
                maintenance_active=maintenance_active,
                active_workload_count=0 if node.state is NodeState.MAINTENANCE else None,
            )
        )
        explanation = explain_heartbeat_decision(
            node_id=node_id,
            payload=payload,
            prior_state=node.state,
            decision=decision,
            retained_evidence={reason: node.reason_evidence.get(reason, ()) for reason in retained},
            retained_observations={reason: node.reason_observations.get(reason, {}) for reason in retained},
            policy_version=self._policy_version,
        ).as_document()
        if boot_change:
            explanation["observedValues"].update(
                {
                    "priorBootSessionId": node.current_boot_session_id,
                    "previousBootSessionId": payload.previous_boot_session_id,
                    "stateLoss": payload.state_loss,
                    "evidenceEpoch": node.evidence_epoch + 1,
                }
            )
        result = HeartbeatResult(
            event_id=payload.event_id,
            node_id=node_id,
            outcome="BOOT_CHANGE_DETECTED" if boot_change else "APPLIED",
            node_revision=node.revision + 1,
            state=decision.state,
            cordoned=decision.cordoned,
            connectivity_status=ConnectivityStatus.ONLINE,
            accepted_at=at,
            explanation=explanation,
        )
        observed = tuple(reason for reason in decision.reason_codes if reason in current_reasons)
        commit = _commit(
            node,
            payload,
            payload_hash,
            decision,
            observed,
            closed,
            explanation,
            result,
            at,
            evidence_epoch=node.evidence_epoch + 1 if boot_change else node.evidence_epoch,
            retained_status_reasons=retained_status_reasons,
        )
        return _PreparedHeartbeat(
            cmd=_dummy_cmd(node_id, payload), result=result, commit=commit, observe_payload=payload
        )

    def _late(
        self, node: NodeSnapshot, payload: HeartbeatPayload, payload_hash: str, at: datetime
    ) -> tuple[HeartbeatResult, IgnoredHeartbeatCommit]:
        evidence_ids = [str(payload.event_id)]
        if node.current_heartbeat_event_id:
            evidence_ids.append(node.current_heartbeat_event_id)
        explanation = Explanation(
            rule_ids=("ERR_LATE_EVENT",),
            observed_values={
                "occurredAt": payload.occurred_at.isoformat(),
                "sourceSequence": payload.source_sequence,
                "bootSessionId": payload.boot_session_id,
                "currentOccurredAt": node.last_accepted_event_at.isoformat() if node.last_accepted_event_at else None,
                "currentSourceSequence": node.current_source_sequence,
                "currentBootSessionId": node.current_boot_session_id,
                "evidenceEpoch": node.evidence_epoch,
            },
            thresholds={"ordering": {"operator": "newer-than-current", "value": "required"}},
            evidence_ids=tuple(evidence_ids),
            policy_version=self._policy_version,
            prior_state=node.state,
            result_state=node.state,
            expected_state=node.state,
            summary=f"{node.node_id} ignored stale heartbeat {payload.event_id}; current telemetry was preserved.",
        ).as_document()
        result = HeartbeatResult(
            event_id=payload.event_id,
            node_id=node.node_id,
            outcome="LATE_IGNORED",
            node_revision=node.revision,
            state=node.state,
            cordoned=node.cordoned,
            connectivity_status=node.connectivity,
            accepted_at=at,
            explanation=explanation,
        )
        commit = IgnoredHeartbeatCommit(
            node_id=node.node_id,
            payload=payload,
            payload_hash=payload_hash,
            evidence_epoch=node.evidence_epoch,
            explanation=explanation,
            result=result.as_document(),
            at=at,
        )
        return result, commit


def _commit_node(commit: HeartbeatCommit | IgnoredHeartbeatCommit | None) -> str | None:
    if commit is None:
        return None
    if isinstance(commit, HeartbeatCommit):
        return commit.projection.node_id
    return commit.node_id


def _dummy_cmd(node_id: str, payload: HeartbeatPayload) -> Any:
    return type("_Cmd", (), {"node_id": node_id, "payload": payload, "future": None})()


def _commit(
    node: NodeSnapshot,
    payload: HeartbeatPayload,
    payload_hash: str,
    decision: Decision,
    observed_reasons: tuple[ReasonCode, ...],
    closed_reasons: tuple[ReasonCode, ...],
    explanation: Mapping[str, Any],
    result: HeartbeatResult,
    at: datetime,
    evidence_epoch: int,
    retained_status_reasons: tuple[str, ...] = (),
) -> HeartbeatCommit:
    transitioned = (decision.state, decision.cordoned) != (node.state, node.cordoned)
    rule_ids = tuple(explanation["ruleIds"])
    evidence_ids = tuple(explanation["evidenceIds"])
    transition = TransitionRecord(
        source_event_id=payload.event_id,
        prior_state=node.state,
        result_state=decision.state,
        prior_cordoned=node.cordoned,
        result_cordoned=decision.cordoned,
        rule_ids=rule_ids,
        evidence_ids=evidence_ids,
        explanation=explanation,
        occurred_at=at,
    )
    return HeartbeatCommit(
        projection=ProjectionUpdate(
            node_id=node.node_id,
            expected_revision=node.revision,
            state=decision.state,
            cordoned=decision.cordoned,
            connectivity=result.connectivity_status,
            active_reason_codes=tuple(reason.value for reason in decision.reason_codes) + retained_status_reasons,
            current_boot_session_id=payload.boot_session_id,
            last_accepted_event_at=payload.occurred_at,
            last_accepted_receive_at=at,
            evidence_epoch=evidence_epoch,
        ),
        payload=payload,
        payload_hash=payload_hash,
        evidence_epoch=evidence_epoch,
        explanation=explanation,
        transition=transition if transitioned else None,
        # Only reasons this heartbeat re-observed refresh their episode; retained ones are not new evidence.
        alert_reasons=observed_reasons,
        closed_alert_reasons=closed_reasons,
        audit=AuditRecord(
            event_id=payload.event_id,
            event_type="RebootDetected" if result.outcome == "BOOT_CHANGE_DETECTED" else "HeartbeatApplied",
            rule_ids=rule_ids,
            evidence_ids=evidence_ids,
            body={"response": result.as_document(), "transitioned": transitioned},
        ),
        at=at,
        disposition=result.outcome,
    )


def _is_late_current_epoch(node: NodeSnapshot, payload: HeartbeatPayload) -> bool:
    if node.current_boot_session_id is None or payload.boot_session_id != node.current_boot_session_id:
        return False
    if node.last_accepted_event_at is not None and payload.occurred_at < node.last_accepted_event_at:
        return True
    if node.last_accepted_event_at is not None and payload.occurred_at == node.last_accepted_event_at:
        higher_sequence = (
            payload.source_sequence is not None
            and node.current_source_sequence is not None
            and payload.source_sequence > node.current_source_sequence
        )
        if not higher_sequence:
            raise DomainError(
                ErrorCode.ERR_ORDER_AMBIGUOUS,
                f"Heartbeat order cannot be resolved at {payload.occurred_at.isoformat()}; "
                "provide a higher sourceSequence.",
                details={
                    "occurredAt": payload.occurred_at.isoformat(),
                    "sourceSequence": payload.source_sequence,
                    "currentSourceSequence": node.current_source_sequence,
                },
            )
    return bool(
        payload.source_sequence is not None
        and node.current_source_sequence is not None
        and payload.source_sequence <= node.current_source_sequence
    )


def _unknown_node(node_id: str) -> DomainError:
    return DomainError(
        ErrorCode.ERR_UNKNOWN_NODE,
        f"Node {node_id} is not configured in this simulation run.",
        details={"nodeId": node_id},
    )
