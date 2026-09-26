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

## DL-15 — UX correction: ONLINE is connectivity, not node health

- **AI recommendation considered:** Use `ONLINE` as the main healthy-state label because the Phase 2 brief asks for it.
- **Human-directed correction:** Preserve the PRD's canonical `HEALTHY` state and show `ONLINE` only as a separate connectivity/freshness signal.
- **Rationale:** A reachable node may still be degraded, recovering, maintained, or cordoned; conflating connectivity with health would contradict Phase 1.
- **Status:** Substantially improved.

## DL-16 — UX rejection: animated flapping indicator and countdown

- **AI recommendation considered:** Pulse the node card and show a debounce countdown during five-second online/offline alternation.
- **Human-directed correction:** Reject flashing/pulsing and any countdown. Keep the primary label stable, show `CONNECTIVITY UNSTABLE`, and name ODD-5/ODD-6.
- **Rationale:** Animation would create visual oscillation and the countdown would invent an unapproved threshold.
- **Status:** Rejected.

## DL-17 — UX correction: maintenance progress is count-based

- **AI recommendation considered:** Render drain progress as a percentage with an estimated completion time.
- **Human-directed correction:** Show only accepted external/mock workload count, IDs, and update time; no percentage or ETA.
- **Rationale:** Module 3 does not own workload duration or scheduling, and ODD-7 supplies no timeout/estimate policy.
- **Status:** Rejected and corrected for scope/unsupported inference.

## DL-18 — UX correction: atomic fleet snapshots

- **Edge-case finding:** Summary counts could update before cards and alerts, producing a contradictory screen.
- **Human-directed decision:** Bind summary, grid, and alert rail to one fleet evaluation/version and retain the prior complete snapshot during refresh.
- **Rationale:** Operational decisions require a coherent view, not mixed-version telemetry.
- **Status:** Accepted review correction.

## DL-19 — UX correction: reconcile unknown maintenance outcomes

- **Edge-case finding:** A lost command response could invite an unsafe retry.
- **Human-directed decision:** Display `Outcome unknown`, block retry, and reconcile the authoritative lock record/timeline before another command.
- **Rationale:** Prevents duplicate or conflicting maintenance commands without building a scheduler.
- **Status:** Accepted review correction.

## DL-20 — UX rejection: force-cancel stalled workloads

- **Edge-case suggestion:** Add workload termination when drain remains blocked.
- **Human-directed decision:** Reject the control and retain `DRAINING`, external/mock workload evidence, and ODD-7 notice.
- **Rationale:** Termination, checkpointing, and scheduling are explicitly outside Module 3.
- **Status:** Rejected for scope creep.

## DL-21 — Architecture selection: serialized reducer, not mutable CRUD

- **Alternatives considered:** Shared mutable services, full event sourcing, and a per-node serialized reducer with evidence ledger/current projection.
- **Decision:** Adopt the per-node serialized reducer behind hexagonal ports.
- **Rationale:** It makes races and explanations deterministic without adding full replay/snapshot operations beyond the prototype.
- **Status:** Accepted architecture decision.

## DL-22 — Architecture correction: atomic domain unit of work

- **Review finding:** Projection, evidence, alert, lock, and idempotency writes could partially commit.
- **Decision:** Require one DomainUnitOfWork for all outputs of a processed node event; any write failure aborts all.
- **Rationale:** A state without its explanation or idempotency result would corrupt subsequent decisions.
- **Status:** Accepted review correction.

## DL-23 — Architecture correction: one owner for external context

- **Review finding:** Reservation/workload facts appeared both inside Heartbeat and behind an external adapter.
- **Decision:** Normalize embedded facts through one External Context Port with source revision/time; Heartbeat does not own them.
- **Rationale:** Prevents stale overwrite and scope drift into reservation/job ownership.
- **Status:** Accepted review correction.

## DL-24 — Architecture rejection: hard-code flapping window

- **AI recommendation considered:** Select a 30-second sliding window with four transitions.
- **Decision:** Reject the values; preserve the versioned Stability Policy port and ODD-5/ODD-6.
- **Rationale:** Neither authoritative source approves a strategy or numeric threshold.
- **Status:** Rejected.

## DL-25 — Architecture correction: maintenance completion needs observed post-lock zero

- **Edge-case finding:** A pre-lock workload observation could arrive after lock acquisition and falsely complete drain.
- **Decision:** Require source revision increase and both observation and receipt times at/after lock acquisition.
- **Rationale:** Receive order alone cannot prove the zero-workload fact describes the drain period.
- **Status:** Accepted review correction.

## DL-26 — Architecture correction: policy-version provenance

- **Review finding:** Decision Records cited facts but not the exact interval/mapping/stabilization configuration.
- **Decision:** Add immutable PolicyConfig and cite its version in every reducer decision.
- **Rationale:** Reproduction and explanation require the rules as well as the inputs.
- **Status:** Accepted review correction.

## DL-27 — Architecture rejection: physical NVML fallback

- **Edge-case suggestion:** Query physical GPU state when simulated samples are missing.
- **Decision:** Reject the adapter; preserve absent/last-known data and safe cordon behavior.
- **Rationale:** Physical NVIDIA dependency violates the authoritative hardware-agnostic constraint.
- **Status:** Rejected.

## DL-28 — Architecture correction: maintenance release is a reducer choice

- **Review finding:** The initial diagram could be implemented as a transient persisted `UNKNOWN` state on release.
- **Decision:** Replace it with a non-persisted choice node whose guarded result commits with lock removal.
- **Rationale:** Release must reevaluate existing facts without generating a false intermediate state.
- **Status:** Accepted review correction.

## DL-29 — Architecture correction: maintenance workload evidence is total

- **Independent finding:** An active lock with missing/stale workload evidence could fall through to a non-maintenance state.
- **Decision:** Make such evidence select `DRAINING` with `DRAIN_STATUS_UNKNOWN`; only fresh post-lock zero selects `MAINTENANCE`.
- **Rationale:** Maintenance precedence must cover positive, zero, and unknown evidence without releasing cordon.
- **Status:** Accepted blocking correction.

## DL-30 — Architecture correction: raw connectivity is evidence-only

- **Independent finding:** Raw five-second observations could oscillate public ConnectivityStatus before ODD-5 classification.
- **Decision:** Raw observations cannot mutate NodeState, ConnectivityStatus, cordon, or AlertEpisode; an approved policy must classify them first.
- **Rationale:** Prevents visible oscillation and implicit thresholds while leaving ODD-5 explicit.
- **Status:** Accepted blocking correction.

## DL-31 — Architecture correction: fleet Tick publication barrier

- **Independent finding:** A Tick could expose mixed pre/post-evaluation states across 32 nodes.
- **Decision:** Publish a Tick fleet version only after all 32 node processors record outcomes; serve the prior complete version meanwhile.
- **Rationale:** Matches the UX atomic snapshot contract and prevents contradictory counts/cards.
- **Status:** Accepted blocking correction.

## DL-32 — Architecture correction: reboot evidence epochs

- **Independent finding:** A state-loss marker without a changed boot ID could allow older events to refill cleared fields.
- **Decision:** Increment a monotonic evidence epoch for every accepted successor session or explicit marker; older-epoch events cannot mutate state.
- **Rationale:** Makes state loss deterministic for both supported evidence forms.
- **Status:** Accepted blocking correction.

## DL-33 — Architecture rejection: remove authoritative storage capacities

- **Review suggestion:** Treat 500 GB workstation and 4 TB server storage capacities as invented.
- **Decision:** Reject the suggestion and retain the values.
- **Rationale:** The fleet topology in `Task plan 2.pdf` explicitly supplies those capacities.
- **Status:** Rejected using authoritative source evidence.

## DL-34 — Readiness gate refuses unsupported PASS

- **Gate evidence:** The mandatory flapping UX contradicts the architecture while ODD-5 is unresolved; ODD-8, NFR-11, and NFR-12/ODD-2 also require approval before implementation readiness.
- **Decision:** Set Phase 4 readiness to `FAIL`, preserve closed Phase 1–3 artifacts, and do not invent policies to manufacture PASS.
- **Rationale:** The assignment permits FAIL and explicitly forbids unsupported thresholds or behavior. Human authority is required for four blockers before implementation begins.
- **Status:** Accepted gate decision; implementation sign-off withheld.

## DL-35 — Readiness correction: unresolved flapping is evidence-only

- **Blocker:** RG-B01 found that UX promised `CONNECTIVITY UNSTABLE`, cordon, and an alert before ODD-5 could classify the raw five-second sequence.
- **Human-directed correction:** Align UX with the PRD/architecture safe hold: preserve public state, connectivity, and cordon; retain raw observations; upsert one policy-unresolved diagnostic; create zero flapping alerts until an approved policy classifies the evidence.
- **Rationale:** This meets the mandatory no-oscillation/no-flood outcome without inventing a debounce or hysteresis threshold.
- **Status:** Accepted; RG-B01 resolved.

## DL-36 — Readiness correction: normalized prototype driver health

- **Blocker:** RG-B02 treated the absence of vendor driver codes as preventing a healthy simulated fleet.
- **Human-directed correction:** Close the hardware-agnostic prototype contract to `HEALTHY`, `UNHEALTHY`, and `UNKNOWN`; reject other heartbeat values and leave vendor-code adapters deferred.
- **Rationale:** Driver health is mandatory existing telemetry, and the normalized health meanings already exist in the PRD state logic; no vendor or physical-GPU behavior is added.
- **Status:** Accepted; RG-B02 resolved.

## DL-37 — Readiness correction: do not invent a latency SLA

- **Blocker:** RG-B03 arose because NFR-11 made an unsupported numeric latency SLA a prerequisite to implementation.
- **Human-directed correction:** Replace that invented prerequisite with the existing atomic-exposure invariant: 100% of mandatory-scenario results commit before their fleet version is exposed. Record baseline latency during implementation; approve any later SLA separately.
- **Rationale:** The official sources supply no time budget, and implementation readiness does not require manufacturing one.
- **Status:** Accepted; RG-B03 resolved with a non-blocking measurement follow-up.

## DL-38 — Readiness correction: process-local persistence boundary

- **Blocker:** RG-B04 promoted unspecified production retention, replay, and capacity limits into prerequisites for a standalone in-memory prototype.
- **Human-directed correction:** Bind the baseline to exactly one current projection per each of 32 nodes, zero durable-history claims, and canonical reset on restart. Defer numeric in-session history, replay-window, pagination, and input-size hardening with explicit non-claims and atomic validation.
- **Rationale:** This uses the already-selected in-memory boundary, avoids infinite-retention claims, and adds no production scope or arbitrary limits.
- **Status:** Accepted; RG-B04 resolved with non-blocking hardening follow-ups.
