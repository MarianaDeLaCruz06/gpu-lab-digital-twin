from __future__ import annotations

import threading
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from gpu_lab_twin.domain.errors import DomainError, ErrorCode
from gpu_lab_twin.domain.explanation import explain_heartbeat_decision
from gpu_lab_twin.domain.fleet import FleetInventory
from gpu_lab_twin.domain.heartbeat import HeartbeatPayload
from gpu_lab_twin.domain.heartbeat_policy import check_boot_succession, reasons_from, validate_heartbeat
from gpu_lab_twin.domain.node import NodeSnapshot
from gpu_lab_twin.domain.node_state import ConnectivityStatus, Decision, NodeFacts, ReasonCode, evaluate
from gpu_lab_twin.ports.inbound.heartbeat import HeartbeatResult
from gpu_lab_twin.ports.outbound.clock import Clock
from gpu_lab_twin.ports.outbound.node_repository import (
    AuditRecord,
    HeartbeatCommit,
    NodeRepository,
    ProjectionUpdate,
    TransitionRecord,
)


class HeartbeatService:
    """Implements HeartbeatPort.

    ``write_lock`` is the process-wide serialization point (AD-1): each node is reduced one event at
    a time and ingest offsets are assigned in order. The repository's revision CAS is the final guard.
    """

    def __init__(
        self,
        *,
        inventory: FleetInventory,
        nodes: NodeRepository,
        clock: Clock,
        policy_version: str,
        write_lock: threading.Lock,
    ) -> None:
        self._inventory = inventory
        self._nodes = nodes
        self._clock = clock
        self._policy_version = policy_version
        self._write_lock = write_lock

    def ingest_heartbeat(self, node_id: str, payload: HeartbeatPayload) -> HeartbeatResult:
        spec = self._inventory.node(node_id)
        if spec is None:
            raise _unknown_node(node_id)
        payload_hash = payload.canonical_hash(node_id)

        with self._write_lock:
            # Read time under the lock so commit order equals receive order.
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
                return HeartbeatResult.from_document(recorded.response, outcome="DUPLICATE")

            node = self._nodes.get_node(node_id)
            if node is None:
                raise _unknown_node(node_id)
            if node.last_accepted_receive_at is not None and at < node.last_accepted_receive_at:
                raise DomainError(
                    ErrorCode.ERR_CLOCK_ORDER,
                    f"Time {at.isoformat()} must be later than {node.last_accepted_receive_at.isoformat()}.",
                    details={"supplied": at.isoformat(), "lastAccepted": node.last_accepted_receive_at.isoformat()},
                )
            check_boot_succession(node, payload)

            prior_reasons = frozenset(ReasonCode(code) for code in node.active_reason_codes)
            current_reasons = reasons_from(payload)
            closed: tuple[ReasonCode, ...] = ()
            if ReasonCode.SILENT in prior_reasons:
                # Telemetry returned after OFFLINE: silence is over, but recovery needs ODD-3 evidence (I-T6).
                prior_reasons -= {ReasonCode.SILENT}
                current_reasons |= {ReasonCode.RECOVERY_PENDING}
                closed = (ReasonCode.SILENT,)
            retained = prior_reasons - current_reasons
            decision = evaluate(NodeFacts(has_current_heartbeat=True, reasons=prior_reasons | current_reasons))
            explanation = explain_heartbeat_decision(
                node_id=node_id,
                payload=payload,
                prior_state=node.state,
                decision=decision,
                retained_evidence={reason: node.reason_evidence.get(reason, ()) for reason in retained},
                policy_version=self._policy_version,
            ).as_document()
            result = HeartbeatResult(
                event_id=payload.event_id,
                node_id=node_id,
                outcome="APPLIED",
                node_revision=node.revision + 1,
                state=decision.state,
                cordoned=decision.cordoned,
                connectivity_status=ConnectivityStatus.ONLINE,
                accepted_at=at,
                explanation=explanation,
            )
            observed = tuple(reason for reason in decision.reason_codes if reason in current_reasons)
            self._nodes.commit_heartbeat(
                _commit(node, payload, payload_hash, decision, observed, closed, explanation, result, at)
            )
            return result


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
            active_reason_codes=tuple(decision.reason_codes),
            current_boot_session_id=payload.boot_session_id,
            last_accepted_event_at=payload.occurred_at,
            last_accepted_receive_at=at,
        ),
        payload=payload,
        payload_hash=payload_hash,
        evidence_epoch=node.evidence_epoch,
        explanation=explanation,
        transition=transition if transitioned else None,
        # Only reasons this heartbeat re-observed refresh their episode; retained ones are not new evidence.
        alert_reasons=observed_reasons,
        closed_alert_reasons=closed_reasons,
        audit=AuditRecord(
            event_id=payload.event_id,
            event_type="HeartbeatApplied",
            rule_ids=rule_ids,
            evidence_ids=evidence_ids,
            body={"response": result.as_document(), "transitioned": transitioned},
        ),
        at=at,
    )


def _unknown_node(node_id: str) -> DomainError:
    return DomainError(
        ErrorCode.ERR_UNKNOWN_NODE,
        f"Node {node_id} is not configured in this simulation run.",
        details={"nodeId": node_id},
    )
