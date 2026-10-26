"""Structured decision explanations (ARCHITECTURE §10, ExplanationDTO)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from gpu_lab_twin.domain.heartbeat import HeartbeatPayload
from gpu_lab_twin.domain.heartbeat_policy import RECOVERY_POLICY_ID
from gpu_lab_twin.domain.node_state import DEGRADATION_REASONS, Decision, NodeState, ReasonCode


class ExplanationIncomplete(ValueError):
    """An automated decision may not be committed without rule, evidence, and summary."""


@dataclass(frozen=True, slots=True)
class Explanation:
    rule_ids: tuple[str, ...]
    observed_values: Mapping[str, Any]
    thresholds: Mapping[str, Any]
    evidence_ids: tuple[str, ...]
    policy_version: str
    prior_state: NodeState
    result_state: NodeState
    summary: str
    expected_state: NodeState | None = field(default=None)

    def __post_init__(self) -> None:
        if not self.rule_ids or not self.evidence_ids or not self.summary.strip() or not self.policy_version:
            raise ExplanationIncomplete("explanation requires rule IDs, evidence IDs, policy version and a summary")
        if len(self.summary) > 1000:
            raise ExplanationIncomplete("explanation summary exceeds 1000 characters")

    def as_document(self) -> dict[str, Any]:
        """The contract ExplanationDTO shape, also persisted verbatim with history/telemetry rows."""
        return {
            "ruleIds": list(self.rule_ids),
            "observedValues": dict(self.observed_values),
            "thresholds": dict(self.thresholds),
            "expectedState": self.expected_state.value if self.expected_state else None,
            "evidenceIds": list(self.evidence_ids),
            "policyVersion": self.policy_version,
            "priorState": self.prior_state.value,
            "resultState": self.result_state.value,
            "summary": self.summary,
        }


UNRESOLVED_CLEAR_RULE = "ERR_POLICY_UNRESOLVED"


def explain_heartbeat_decision(
    *,
    node_id: str,
    payload: HeartbeatPayload,
    prior_state: NodeState,
    decision: Decision,
    retained_evidence: Mapping[ReasonCode, tuple[str, ...]],
    policy_version: str,
) -> Explanation:
    """Render the reducer's decision for one accepted heartbeat from the facts it evaluated.

    ``retained_evidence`` maps each reason kept from earlier heartbeats to the evidence that activated it,
    so the explanation cites every fact the reducer used, not only the current heartbeat.
    """
    retained_reasons = frozenset(retained_evidence)
    observed: dict[str, Any] = {
        "driverHealth": payload.driver_health.value,
        "temperatureC": payload.max_temperature_c,
        "gpuSamples": [
            {"gpuDeviceId": s.gpu_device_id, "temperatureC": s.temperature_c, "vramOccupiedGb": s.vram_occupied_gb}
            for s in payload.gpu_samples
        ],
        "storageFreeGb": payload.storage_free_gb,
        "bootSessionId": payload.boot_session_id,
        "occurredAt": payload.occurred_at.isoformat(),
    }
    thresholds: dict[str, Any] = {}
    rule_ids = list(decision.rule_ids)

    if DEGRADATION_REASONS & set(decision.reason_codes):
        thresholds["driverHealth"] = {"operator": "==", "value": "HEALTHY"}
    if ReasonCode.RECOVERY_PENDING in decision.reason_codes:
        thresholds["recoveryPolicy"] = {"policyId": RECOVERY_POLICY_ID, "status": "unresolved"}
    evidence_ids = [str(payload.event_id)]
    if retained_reasons:
        rule_ids.append(UNRESOLVED_CLEAR_RULE)
        thresholds["clearPolicy"] = "unresolved"
        observed["retainedReasonEvidence"] = {
            reason.value: list(retained_evidence[reason]) for reason in sorted(retained_reasons)
        }
        for reason in sorted(retained_reasons):
            evidence_ids.extend(e for e in retained_evidence[reason] if e not in evidence_ids)

    return Explanation(
        rule_ids=tuple(rule_ids),
        observed_values=observed,
        thresholds=thresholds,
        evidence_ids=tuple(evidence_ids),
        policy_version=policy_version,
        prior_state=prior_state,
        result_state=decision.state,
        expected_state=decision.state,
        summary=_summary(node_id, decision, retained_reasons),
    )


def _summary(node_id: str, decision: Decision, retained: frozenset[ReasonCode]) -> str:
    eligibility = "cordoned from new work" if decision.cordoned else "eligible for new work"
    if not decision.reason_codes:
        return (
            f"{node_id} is {decision.state} and {eligibility}: a current heartbeat was accepted with no active reason."
        )
    reasons = ", ".join(decision.reason_codes)
    text = f"{node_id} is {decision.state} and {eligibility} because of active reason(s) {reasons}."
    if retained:
        text += f" {', '.join(sorted(retained))} retained: no approved clear rule exists yet."
    return text


def explain_silence(
    *,
    node_id: str,
    prior_state: NodeState,
    decision: Decision,
    last_accepted_receive_at: datetime,
    evaluation_at: datetime,
    heartbeat_interval_ms: int,
    missed_intervals: float,
    evidence_ids: tuple[str, ...],
    retained_evidence: Mapping[ReasonCode, tuple[str, ...]],
    policy_version: str,
) -> Explanation:
    """Explain an AD-2 silence transition with the exact comparison the rule made.

    Lower-precedence reasons stay active under OFFLINE; they and the evidence that activated them are cited too.
    """
    elapsed = evaluation_at - last_accepted_receive_at
    elapsed_seconds = elapsed.total_seconds()
    interval_seconds = heartbeat_interval_ms / 1000
    observed: dict[str, Any] = {
        "lastAcceptedReceiveAt": last_accepted_receive_at.isoformat(),
        "evaluationAt": evaluation_at.isoformat(),
        "elapsedSeconds": elapsed_seconds,
        "elapsedMicroseconds": elapsed // timedelta(microseconds=1),
        "heartbeatIntervalMs": heartbeat_interval_ms,
        "missedIntervals": missed_intervals,
    }
    all_evidence = list(evidence_ids)
    summary_tail = ""
    if retained_evidence:
        observed["retainedReasonEvidence"] = {
            reason.value: list(ids) for reason, ids in sorted(retained_evidence.items())
        }
        for ids in retained_evidence.values():
            all_evidence.extend(e for e in ids if e not in all_evidence)
        summary_tail = f" Still active: {', '.join(sorted(r.value for r in retained_evidence))}."
    return Explanation(
        rule_ids=decision.rule_ids,
        observed_values=observed,
        thresholds={"missedIntervals": {"operator": ">", "value": 3}},
        evidence_ids=tuple(all_evidence),
        policy_version=policy_version,
        prior_state=prior_state,
        result_state=decision.state,
        expected_state=decision.state,
        summary=(
            f"{node_id} is {decision.state} and cordoned from new work because elapsed silence "
            f"{elapsed_seconds:g} s was greater than 3 x interval {interval_seconds:g} s "
            f"({missed_intervals:g} missed intervals).{summary_tail}"
        ),
    )
