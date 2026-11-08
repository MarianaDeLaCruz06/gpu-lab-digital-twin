from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from uuid import UUID

from gpu_lab_twin.domain.connectivity_policy import ConnectivityObservation, evaluate_connectivity
from gpu_lab_twin.domain.errors import DomainError, ErrorCode
from gpu_lab_twin.ports.inbound.connectivity import ConnectivityResult
from gpu_lab_twin.ports.outbound.clock import Clock
from gpu_lab_twin.ports.outbound.node_repository import ConnectivityObservationCommit, NodeRepository


class ConnectivityService:
    """Ordered evidence ingestion for AD-5 without inventing the unresolved flapping classifier."""

    def __init__(
        self,
        *,
        nodes: NodeRepository,
        clock: Clock,
        policy_version: str,
        write_lock: threading.Lock,
    ) -> None:
        self._nodes = nodes
        self._clock = clock
        self._policy_version = policy_version
        self._write_lock = write_lock

    def observe(
        self,
        node_id: str,
        *,
        event_id: UUID,
        status: ConnectivityObservation | str,
        observed_at: datetime,
    ) -> ConnectivityResult:
        try:
            observation = ConnectivityObservation(status)
        except ValueError as exc:
            raise DomainError(
                ErrorCode.ERR_SCHEMA,
                "Connectivity status must be ONLINE or OFFLINE.",
                details={"field": "status", "supplied": str(status)},
            ) from exc
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise DomainError(
                ErrorCode.ERR_SCHEMA,
                "observed_at must be a timezone-aware instant.",
                details={"field": "observedAt"},
            )

        observation_hash = _observation_hash(node_id, observation, observed_at)
        with self._write_lock:
            accepted_at = self._clock.now()
            if observed_at > accepted_at:
                raise DomainError(
                    ErrorCode.ERR_CLOCK_ORDER,
                    f"Observation time {observed_at.isoformat()} is later than {accepted_at.isoformat()}.",
                    details={"supplied": observed_at.isoformat(), "now": accepted_at.isoformat()},
                )
            recorded = self._nodes.find_connectivity_observation(event_id)
            if recorded is not None:
                if recorded.observation_hash != observation_hash:
                    raise DomainError(
                        ErrorCode.ERR_IDEMPOTENCY_CONFLICT,
                        f"{event_id} was already used for different connectivity evidence.",
                        details={"eventId": str(event_id), "recordedNodeId": recorded.node_id},
                    )
                return ConnectivityResult.from_document(recorded.response, outcome="DUPLICATE")

            node = self._nodes.get_node(node_id)
            if node is None:
                raise DomainError(
                    ErrorCode.ERR_UNKNOWN_NODE,
                    f"Node {node_id} is not configured in this simulation run.",
                    details={"nodeId": node_id},
                )
            prior_observation = node.reason_observations.get(ErrorCode.ERR_POLICY_UNRESOLVED.value, {})
            prior_observed_at = prior_observation.get("observedAt")
            if prior_observed_at is not None and observed_at < datetime.fromisoformat(prior_observed_at):
                raise DomainError(
                    ErrorCode.ERR_CLOCK_ORDER,
                    f"Observation time {observed_at.isoformat()} is earlier than {prior_observed_at}.",
                    details={"supplied": observed_at.isoformat(), "lastAccepted": prior_observed_at},
                )

            decision = evaluate_connectivity(observation)
            explanation = {
                "ruleIds": [decision.reason_code.value],
                "observedValues": {"connectivityObservation": observation.value, "observedAt": observed_at.isoformat()},
                "thresholds": {"policyId": decision.policy_id, "status": "UNRESOLVED"},
                "expectedState": node.state.value,
                "evidenceIds": [str(event_id)],
                "policyVersion": self._policy_version,
                "priorState": node.state.value,
                "resultState": node.state.value,
                "summary": (
                    "ODD-5 is unresolved; raw connectivity evidence was retained while the stable public "
                    "state, connectivity, cordon, and eligibility were held."
                ),
            }
            result = ConnectivityResult(
                event_id=event_id,
                node_id=node_id,
                outcome="HELD_POLICY_UNRESOLVED",
                node_revision=node.revision,
                state=node.state,
                cordoned=node.cordoned,
                connectivity_status=node.connectivity,
                accepted_at=accepted_at,
                observation=observation,
                reason_code=decision.reason_code,
                policy_id=decision.policy_id,
                explanation=explanation,
            )
            self._nodes.commit_connectivity_observation(
                ConnectivityObservationCommit(
                    event_id=event_id,
                    node_id=node_id,
                    observation_hash=observation_hash,
                    observed_at=observed_at,
                    accepted_at=accepted_at,
                    observation=observation.value,
                    reason_code=decision.reason_code.value,
                    explanation=explanation,
                    response=result.as_document(),
                )
            )
            return result


def _observation_hash(node_id: str, status: ConnectivityObservation, observed_at: datetime) -> str:
    document = {
        "nodeId": node_id,
        "status": status.value,
        "observedAt": observed_at.astimezone(UTC).isoformat(),
    }
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
