# Epic 2 Context: Automated Node Protection and Recovery

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Carlos (Hardware Lab Technician) and Alex (Graduate Researcher) get stable, explainable protection when lab hardware misbehaves: an overheating GPU is contained automatically, a rebooted workstation is shown as recovering rather than healthy, and five-second connectivity flapping does not make the fleet oscillate or flood alerts. Every protection is a reason the shared reducer evaluates, so nodes are never advertised as eligible while unsafe.

## Stories

- Story 2.1: Cordon an overheating workstation
- Story 2.2: Explain workstation reboot recovery
- Story 2.3: Contain five-second connectivity flapping

## Requirements & Constraints

- Thermal rule: any accepted GPU temperature strictly greater than 88 °C activates the thermal reason (`ERR_THERMAL_88`). Exactly 88.0 °C does not. One hot GPU affects the whole node (the dual-GPU server is cordoned as a unit).
- The thermal reason, `cordoned=true`, the precedence-selected state, and an explanation citing GPU, observed value, `>` 88 threshold, and rule commit atomically before any read can see the node. No response may show a hot node as eligible.
- Externally visible state is `DEGRADED` unless a higher-precedence state applies (maintenance, `OFFLINE`, `RECOVERING`). Higher precedence never deletes the thermal reason.
- Thermal clearing (ODD-4: release temperature, sample count, acknowledgement) is unresolved. Until it is approved, the reason and cordon are retained and the explanation says the clear policy is unresolved.
- Reboot detection needs explicit succession proof (`previousBootSessionId` or `stateLoss`), increments an evidence epoch once, and yields `RECOVERING`. Recovery exit (ODD-3) is unresolved, and older-session telemetry can never refill state.
- Raw connectivity observations are evidence only while ODD-5 is unresolved. They produce no public state change, no flapping alert, and at most one current `ERR_POLICY_UNRESOLVED` diagnostic.
- At most one open alert episode per (node, reason). Equivalent observations update it, and a recurrence after closure opens a new one.

## Technical Decisions

- Reducer precedence: `DRAINING > MAINTENANCE > OFFLINE > RECOVERING > DEGRADED > HEALTHY > UNKNOWN`. Handlers only contribute reasons, every non-`HEALTHY` state is cordoned (also a DB check constraint), and lower-precedence reasons are retained.
- Reasons persist in `nodes.active_reason_codes`. An open `alerts` row per reason holds the evidence that last observed it, so retained-reason explanations can cite the activating event.
- Heartbeat ingestion is one compare-and-swap transaction: projection, telemetry snapshot plus GPU samples, history row only on state/cordon change, alert upserts for reasons re-observed by this heartbeat, and an audit row.
- Explanations follow the `ExplanationDTO` contract: `ruleIds`, `observedValues`, `thresholds` (for thermal: `{"temperatureC": {"operator": ">", "value": 88}}`), `evidenceIds`, `policyVersion`, prior/result/expected state, and `summary`.
- No new endpoints are needed for Epic 2's heartbeat-driven protections. `cordoned` is the eligibility signal consumed by other modules.

## Cross-Story Dependencies

- Builds on Epic 1's heartbeat path, reducer, alert episodes, and silence/recovery reasons (`ERR_SILENT`, `RECOVERY_PENDING`).
- 2.1 → 2.2 → 2.3 in order. 2.2 will replace the fail-closed reboot handling that Story 1.1 currently returns as `ERR_POLICY_UNRESOLVED`.
