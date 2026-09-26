# AI Decision Log — GPU Lab Digital Twin

Date: 2026-09-26  
Phase: 1 — PRD & Capability Scoping

This log records human-directed constraints and corrections applied to AI-assisted planning. “Human direction” refers to the assignment instructions supplied for this run.

## DL-01 — Strict Module 3 ownership boundary

- **Human direction:** Scope the PRD strictly to the GPU Lab Digital Twin and do not integrate other student modules.
- **Decision:** The twin owns node health/state representation, transition history, eligibility/cordon status, and simulated fault inputs only.
- **Rationale:** This preserves independent executability and prevents the PRD from becoming a platform-wide specification.
- **Status:** Accepted constraint.

## DL-02 — Reservations are read-only mocked state

- **Human direction:** Reservations may be represented as mocked external state; do not build the GPU Reservation System.
- **Decision:** Heartbeats may carry reservation references for display and explanation, but Module 3 performs no booking, overlap checking, allocation, expiration, or cancellation.
- **Rationale:** Those behaviors belong to Module 4.
- **Status:** Accepted constraint.

## DL-03 — No physical GPU dependency

- **Human direction:** Keep the prototype simulated and hardware-agnostic; do not require a physical NVIDIA GPU.
- **Decision:** Canonical fixtures and the fault generator are sufficient to exercise all requirements; CUDA, NVML, NVIDIA drivers, and GPU access are non-goals.
- **Rationale:** Matches the official independent-prototype and hardware-agnostic constraints.
- **Status:** Accepted constraint.

## DL-04 — Deterministic state machine is mandatory

- **Human direction:** Non-trivial logic must include a deterministic node state machine.
- **Decision:** Define seven mutually exclusive public states, a separate cordon flag, fixed evaluation precedence, and a transition table.
- **Rationale:** Separating representation from eligibility prevents ambiguous mixed states and makes every scenario testable.
- **Status:** Accepted constraint.

## DL-05 — Rejected AI suggestion: choose a 30-second heartbeat

- **AI suggestion considered:** Use a 30-second heartbeat interval and declare a node offline after 90 seconds.
- **Human correction:** The official source specifies only “missing more than 3 intervals”; it does not specify interval duration.
- **Decision:** Record heartbeat duration as ODD-1 and express silence as `elapsed > 3 × configured interval`.
- **Rationale:** Choosing 30 seconds would invent institutional policy and would also incorrectly treat equality at three intervals as qualifying.
- **Status:** Rejected.

## DL-06 — Rejected AI suggestion: use a fixed 20-second flapping debounce

- **AI suggestion considered:** Stabilize connectivity after four five-second observations (20 seconds).
- **Human correction:** The assignment requires prevention of oscillation and flooding but supplies no debounce, count-window, or clearing duration.
- **Decision:** Keep stabilization and alert-repeat policy as ODD-5 and ODD-6; require parameterized tests once approved.
- **Rationale:** An arbitrary value could hide real outages or cause slow recovery and would violate the no-invented-threshold instruction.
- **Status:** Rejected.

## DL-07 — Rejected AI suggestion: embed scheduling in maintenance drain

- **AI suggestion considered:** Have the twin evict, checkpoint, or reschedule active jobs when Carlos starts maintenance.
- **Human correction:** Job scheduling may be mocked/delegated and another module's scheduler must not be built.
- **Decision:** The twin immediately cordons, observes mocked workload counts, reports drain progress, and never emits terminate/checkpoint/placement actions.
- **Rationale:** This preserves Module 3 scope while still proving graceful drain state logic.
- **Status:** Rejected for scope creep.

## DL-08 — State and cordon are separate concepts

- **Human direction:** The twin owns health/state representation and must cordon unsafe nodes.
- **Decision:** Model one deterministic public state plus an independent Boolean cordon flag, with all non-healthy states forcing cordon.
- **Rationale:** A maintenance or recovering node can be represented accurately without conflating health labels with scheduling actions.
- **Status:** Substantially improved from an initial single-enum availability concept.

## DL-09 — Maintenance has representational precedence but not safety amnesia

- **Human direction:** Support Carlos's maintenance drain and safe thermal handling.
- **Decision:** `DRAINING`/`MAINTENANCE` take display precedence while all thermal, driver, silence, and recovery reasons remain retained and must be reevaluated on release.
- **Rationale:** Carlos's explicit lock remains visible, yet releasing it cannot erase unsafe evidence.
- **Status:** Accepted decision.

## DL-10 — Explicit unresolved-policy behavior

- **Human direction:** Do not silently choose missing thresholds; mark them `OPEN DESIGN DECISION`.
- **Decision:** When an unresolved policy is required for an exit transition, the twin holds the safe cordoned state and emits `ERR_POLICY_UNRESOLVED` naming the missing decision.
- **Rationale:** “Unknown” must not degrade into an implicit permissive default.
- **Status:** Accepted decision.

## DL-11 — Adversarial correction: fail closed on unmapped driver health

- **Review finding:** The initial PRD could be read as allowing an unconfigured driver status to pass into `HEALTHY`.
- **Human-directed decision:** Accept the finding and require `ERR_POLICY_UNRESOLVED` plus cordon until the driver vocabulary has an approved health mapping.
- **Rationale:** Unknown safety evidence cannot become an implicit healthy default.
- **Status:** Accepted review correction.

## DL-12 — Adversarial correction: maintenance command authority

- **Review finding:** Heartbeat-observed maintenance status could conflict with Carlos's command record.
- **Human-directed decision:** Accept the finding; Carlos's Module 3 command record is authoritative and a mismatch is surfaced without auto-release.
- **Rationale:** A stale or simulated heartbeat must not remove a deliberate maintenance cordon.
- **Status:** Accepted review correction.

## DL-13 — Adversarial rejection: do not add RBAC to Module 3

- **Review suggestion:** Add identity and role authorization around Carlos's maintenance action.
- **Human-directed decision:** Reject the suggestion for Phase 1 and label authorization external to the standalone named-persona fixture.
- **Rationale:** Building identity/RBAC would violate strict Module 3 scope. The PRD describes the maintenance behavior without claiming production authorization enforcement.
- **Status:** Rejected for scope leakage.

## DL-14 — Adversarial correction: deduplicate alert episodes by node and reason

- **Review finding:** “One evolving alert” did not fully define identity, closure, or recurrence.
- **Human-directed decision:** Accept the finding; allow at most one open episode per `(node_id, reason_code)`, close only under that reason's approved clear rule, and create a new episode for later recurrence.
- **Rationale:** This prevents alert floods without erasing distinct incidents.
- **Status:** Accepted review correction.
