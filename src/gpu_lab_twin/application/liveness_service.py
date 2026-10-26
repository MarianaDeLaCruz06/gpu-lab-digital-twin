from __future__ import annotations

import logging
import threading
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from gpu_lab_twin.domain.errors import DomainError, ErrorCode
from gpu_lab_twin.domain.explanation import explain_silence
from gpu_lab_twin.domain.fleet import FleetInventory
from gpu_lab_twin.domain.heartbeat_policy import is_silent, missed_intervals
from gpu_lab_twin.domain.node import NodeSnapshot
from gpu_lab_twin.domain.node_state import ConnectivityStatus, NodeFacts, ReasonCode, evaluate
from gpu_lab_twin.ports.inbound.liveness import LivenessReport
from gpu_lab_twin.ports.outbound.clock import Clock
from gpu_lab_twin.ports.outbound.node_repository import (
    AuditRecord,
    NodeRepository,
    ProjectionUpdate,
    TransitionCommit,
    TransitionRecord,
)

logger = logging.getLogger(__name__)


class LivenessService:
    """Implements LivenessPort: ordered clock evaluations of AD-2 silence for every configured node.

    Shares the heartbeat ``write_lock`` so a heartbeat received before an evaluation is always applied
    before that evaluation reads the node (ARCHITECTURE §6.2).
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
        self._last_evaluation_at: datetime | None = None

    def evaluate_fleet_liveness(self, evaluation_at: datetime | None = None) -> LivenessReport:
        with self._write_lock:
            now = self._clock.now()
            at = evaluation_at or now
            if at.tzinfo is None or at.utcoffset() is None:
                raise DomainError(
                    ErrorCode.ERR_SCHEMA,
                    "evaluation_at must be a timezone-aware instant.",
                    details={"field": "evaluationAt"},
                )
            if at > now:
                raise DomainError(
                    ErrorCode.ERR_CLOCK_ORDER,
                    f"Time {at.isoformat()} is later than the current instant {now.isoformat()}.",
                    details={"supplied": at.isoformat(), "now": now.isoformat()},
                )
            if self._last_evaluation_at is not None and at <= self._last_evaluation_at:
                raise DomainError(
                    ErrorCode.ERR_CLOCK_ORDER,
                    f"Time {at.isoformat()} must be later than {self._last_evaluation_at.isoformat()}.",
                    details={"supplied": at.isoformat(), "lastAccepted": self._last_evaluation_at.isoformat()},
                )

            transitioned: list[str] = []
            held: list[str] = []
            failed: list[str] = []
            for spec in self._inventory.nodes:
                node = self._nodes.get_node(spec.node_id)
                # The configured inventory interval is authoritative (AD-2), not a possibly stale stored copy.
                if node is None or not is_silent(node.last_accepted_receive_at, at, spec.heartbeat_interval_ms):
                    continue
                if ReasonCode.SILENT.value in node.active_reason_codes:
                    held.append(node.node_id)
                    continue
                try:
                    self._nodes.commit_transition(self._silence_commit(node, at, spec.heartbeat_interval_ms))
                except DomainError as exc:
                    # One node's failed commit must not hide silence on the rest of the fleet.
                    logger.warning("silence transition for %s not committed: %s", node.node_id, exc.code)
                    failed.append(node.node_id)
                    continue
                transitioned.append(node.node_id)

            self._last_evaluation_at = at
            return LivenessReport(
                evaluated_at=at,
                transitioned_node_ids=tuple(transitioned),
                held_node_ids=tuple(held),
                failed_node_ids=tuple(failed),
            )

    def _silence_commit(self, node: NodeSnapshot, at: datetime, interval_ms: int) -> TransitionCommit:
        assert node.last_accepted_receive_at is not None  # is_silent() requires a prior heartbeat
        reasons = frozenset(ReasonCode(code) for code in node.active_reason_codes) | {ReasonCode.SILENT}
        decision = evaluate(NodeFacts(has_current_heartbeat=False, reasons=reasons))
        evaluation_id = uuid5(NAMESPACE_URL, f"urn:gpu-lab-digital-twin:clock:{node.node_id}:{at.isoformat()}")
        evidence = (str(evaluation_id),) + (
            (node.current_heartbeat_event_id,) if node.current_heartbeat_event_id else ()
        )
        retained = {
            reason: tuple(node.reason_evidence.get(reason.value, ()))
            for reason in decision.reason_codes
            if reason is not ReasonCode.SILENT
        }
        explanation = explain_silence(
            node_id=node.node_id,
            prior_state=node.state,
            decision=decision,
            last_accepted_receive_at=node.last_accepted_receive_at,
            evaluation_at=at,
            heartbeat_interval_ms=interval_ms,
            missed_intervals=missed_intervals(node.last_accepted_receive_at, at, interval_ms),
            evidence_ids=evidence,
            retained_evidence=retained,
            policy_version=self._policy_version,
        ).as_document()
        return TransitionCommit(
            projection=ProjectionUpdate(
                node_id=node.node_id,
                expected_revision=node.revision,
                state=decision.state,
                cordoned=decision.cordoned,
                connectivity=ConnectivityStatus.SILENT,
                active_reason_codes=tuple(decision.reason_codes),
                current_boot_session_id=node.current_boot_session_id,
                last_accepted_event_at=node.last_accepted_event_at,
                last_accepted_receive_at=node.last_accepted_receive_at,
            ),
            transition=TransitionRecord(
                source_event_id=evaluation_id,
                prior_state=node.state,
                result_state=decision.state,
                prior_cordoned=node.cordoned,
                result_cordoned=decision.cordoned,
                rule_ids=tuple(explanation["ruleIds"]),
                evidence_ids=tuple(explanation["evidenceIds"]),
                explanation=explanation,
                occurred_at=at,
            ),
            explanation=explanation,
            alert_reasons=(ReasonCode.SILENT,),
            audit=AuditRecord(
                event_id=evaluation_id,
                event_type="NodeSilenceDetected",
                rule_ids=tuple(explanation["ruleIds"]),
                evidence_ids=tuple(explanation["evidenceIds"]),
                # The task annex names this event NODE_SILENT_TIMEOUT; the contract reason code is ERR_SILENT.
                body={
                    "evaluationAt": at.isoformat(),
                    "annexEventName": "NODE_SILENT_TIMEOUT",
                    "explanation": explanation,
                },
            ),
            at=at,
        )
