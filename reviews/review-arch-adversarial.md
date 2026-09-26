# Architecture Review — Adversarial Lens

Date: 2026-09-26  
Artifact: `planning/ARCHITECTURE.md` initial Phase 3 draft  
Lens: BMad `adversarial`

## Verdict

The initial architecture establishes the correct scope and single-writer reducer model, but twelve adversarial findings exposed several places where independently implemented components could still diverge. Nine are accepted and applied, two are deferred to existing open decisions, and one is rejected because it requires inventing the prohibited flapping threshold. No accepted or rejected finding remains blocking after correction.

## Findings

### ARCH-ADV-01

- **Severity:** HIGH
- **Issue:** The state diagram routes maintenance release through `UNKNOWN`, which can be implemented as a real transient state despite the prose disclaimer.
- **Recommendation:** Use an explicit choice/reducer node with guarded results and never persist `UNKNOWN` during release unless no accepted heartbeat exists.
- **Classification:** **ACCEPT**
- **Rationale:** The diagram must not contradict the transition contract or UX.

### ARCH-ADV-02

- **Severity:** HIGH
- **Issue:** Projection, evidence, alerts, and idempotency are named separately without an explicit atomic unit-of-work boundary.
- **Recommendation:** Require one atomic commit across all state-change outputs or no commit.
- **Classification:** **ACCEPT**
- **Rationale:** Partial commits could expose state without evidence or replay the same event twice.

### ARCH-ADV-03

- **Severity:** HIGH
- **Issue:** Clock Tick ordering claims a receive-time barrier but does not define how heartbeat and tick offsets are assigned atomically.
- **Recommendation:** Make the sequencer the sole assigner under one serialization point and define the tie rule.
- **Classification:** **ACCEPT**
- **Rationale:** Silence at the boundary must not depend on thread scheduling.

### ARCH-ADV-04

- **Severity:** HIGH
- **Issue:** Distinct current-session heartbeats with equal `event_time` lack an ordering result.
- **Recommendation:** Add monotonic source sequence when supplied; otherwise classify different-payload equal-time events as ambiguous and fail closed.
- **Classification:** **ACCEPT**
- **Rationale:** Last-write-by-thread would violate deterministic telemetry ordering.

### ARCH-ADV-05

- **Severity:** MEDIUM
- **Issue:** Temperature validation says finite but omits the PRD's non-negative numeric rule.
- **Recommendation:** Require `temperature_c >= 0` in the simulated contract; reject the whole Heartbeat atomically if any GPU sample is invalid.
- **Classification:** **ACCEPT**
- **Rationale:** Architecture contracts must preserve Phase 1 validation rules even if negative physical temperatures are theoretically possible.

### ARCH-ADV-06

- **Severity:** HIGH
- **Issue:** `ONLINE` is declared derived but its precedence relative to silence, flapping, and raw connectivity is not defined.
- **Recommendation:** Define ConnectivityStatus as a reducer-owned projection with explicit precedence and evidence.
- **Classification:** **ACCEPT**
- **Rationale:** Separate UI/application implementations could otherwise report `ONLINE` beside `OFFLINE`.

### ARCH-ADV-07

- **Severity:** HIGH
- **Issue:** Reservation/workload context appears both inside Heartbeat and behind an external adapter, creating two potential owners.
- **Recommendation:** Normalize embedded context through one External Context port with source revision/time; never let Heartbeat own it.
- **Classification:** **ACCEPT**
- **Rationale:** Module boundaries and stale ordering require one source of mutation authority.

### ARCH-ADV-08

- **Severity:** HIGH
- **Issue:** Rule and policy values used by the reducer are not bound to an immutable configuration version in Decision Records.
- **Recommendation:** Create a versioned PolicyConfig snapshot and cite its ID in every decision.
- **Classification:** **ACCEPT**
- **Rationale:** Replaying or explaining a decision requires the exact interval, threshold rule, mappings, and strategy version.

### ARCH-ADV-09

- **Severity:** MEDIUM
- **Issue:** Alert recurrence after closure is not stated in the architecture, only the one-open-episode constraint.
- **Recommendation:** Require a new episode ID after a reason closes and later reactivates.
- **Classification:** **ACCEPT**
- **Rationale:** Otherwise separate incidents could be merged indefinitely.

### ARCH-ADV-10

- **Severity:** MEDIUM
- **Issue:** Alert/history pagination and capacity are unspecified.
- **Recommendation:** Choose numeric retention and cursor behavior before implementation readiness.
- **Classification:** **DEFER**
- **Rationale:** PRD NFR-12 intentionally leaves these numeric values open; the API makes no complete-history claim.

### ARCH-ADV-11

- **Severity:** MEDIUM
- **Issue:** The prototype lacks an absolute decision-latency/backpressure target.
- **Recommendation:** Approve NFR-11 latency and sample size, then bind admission/backpressure tests to it.
- **Classification:** **DEFER**
- **Rationale:** The source supplies no value and Phase 3 cannot invent one.

### ARCH-ADV-12

- **Severity:** HIGH
- **Issue:** A reviewer proposes selecting a 30-second sliding window and four transitions for flapping now.
- **Recommendation:** Hard-code those values so the mandatory scenario can run without configuration.
- **Classification:** **REJECT**
- **Rationale:** This would silently invent ODD-5 values. The explicit strategy port, fail-closed state, and parameterized future test are the correct boundary.

## Independent verification findings

### ARCH-ADV-13

- **Severity:** CRITICAL
- **Issue:** Active maintenance with missing/stale workload evidence matched neither positive nor zero and could fall through precedence.
- **Recommendation:** Make unknown/stale/pre-lock evidence select `DRAINING` with `DRAIN_STATUS_UNKNOWN`.
- **Classification:** **ACCEPT**
- **Rationale:** An active lock must always retain cordon and a maintenance-related state.

### ARCH-ADV-14

- **Severity:** CRITICAL
- **Issue:** Raw alternating connectivity observations could still alternate the public ConnectivityStatus before ODD-5 classification.
- **Recommendation:** Keep raw observations evidence-only and retain the last stable public connectivity value until an approved policy classifies them.
- **Classification:** **ACCEPT**
- **Rationale:** This closes the mandatory visible-oscillation path without inventing a threshold.

### ARCH-ADV-15

- **Severity:** HIGH
- **Issue:** Thermal/driver transition rows selected `DEGRADED` directly despite higher maintenance/recovery precedence.
- **Recommendation:** Activate reason/cordon atomically, then route target through full precedence.
- **Classification:** **ACCEPT**
- **Rationale:** Compound events must produce one reducer-selected visible state.

### ARCH-ADV-16

- **Severity:** MEDIUM
- **Issue:** Reviewer challenged the 500 GB workstation and 4 TB server storage capacities as invented.
- **Recommendation:** Remove the capacities from the fixture.
- **Classification:** **REJECT**
- **Rationale:** `Task plan 2.pdf` explicitly specifies 500 GB NVMe per workstation and 4 TB NVMe for the server.

### ARCH-ADV-17

- **Severity:** HIGH
- **Issue:** Malformed embedded reservation/workload facts could reject valid heartbeat telemetry.
- **Recommendation:** Extract separately identified external events and validate/commit them independently from telemetry.
- **Classification:** **ACCEPT**
- **Rationale:** External context has separate ownership and must not cause false telemetry silence.

### ARCH-ADV-18

- **Severity:** HIGH
- **Issue:** Unresolved driver vocabulary could block every required Heartbeat.
- **Recommendation:** Accept a syntactically valid nonempty code and fail closed only at semantic mapping.
- **Classification:** **ACCEPT**
- **Rationale:** ODD-8 defers meaning, not ingestion of the remaining valid telemetry.

### ARCH-ADV-19

- **Severity:** CRITICAL
- **Issue:** A Clock Tick could publish a fleet projection after only some node processors completed.
- **Recommendation:** Publish a Tick fleet version only after a 32-node completion barrier.
- **Classification:** **ACCEPT**
- **Rationale:** UX requires one atomic fleet evaluation/version.

### ARCH-ADV-20

- **Severity:** MEDIUM
- **Issue:** A returning current heartbeat did not explicitly close the silent-node alert episode.
- **Recommendation:** Close silence in the same unit of work that enters recovery.
- **Classification:** **ACCEPT**
- **Rationale:** Recovery and a stale open silence incident must not coexist without explanation.

### ARCH-ADV-21

- **Severity:** MEDIUM
- **Issue:** Workload API validation used `observed_at`, but its input list omitted the field.
- **Recommendation:** Add `observed_at` with simulated clock/timezone semantics.
- **Classification:** **ACCEPT**
- **Rationale:** Drain freshness must be implementable from the declared contract.

### ARCH-ADV-22

- **Severity:** MEDIUM
- **Issue:** Maintenance Lock ownership was split between application service and Node Event Processor.
- **Recommendation:** Make the processor/aggregate sole writer and application service command router only.
- **Classification:** **ACCEPT**
- **Rationale:** Single-writer ownership must be consistent across topology, data model, and invariant.

### ARCH-ADV-23

- **Severity:** MEDIUM
- **Issue:** The state diagram omitted direct-to-maintenance and unknown-evidence maintenance paths.
- **Recommendation:** Route lock acquisition through a reducer choice for `DRAINING` versus `MAINTENANCE`.
- **Classification:** **ACCEPT**
- **Rationale:** Diagram and transition table must encode the same guards.

### ARCH-ADV-24

- **Severity:** CRITICAL
- **Issue:** “Contradictory” raw connectivity evidence implicitly forced cordon without a defined classification rule.
- **Recommendation:** Preserve evidence and public values until an approved ODD-5 policy classifies flapping.
- **Classification:** **ACCEPT**
- **Rationale:** A safety mutation cannot depend on an undefined threshold; implementation readiness remains blocked on ODD-5, not Phase 3 closure.

## Counts

- **Total:** 24
- **Accepted:** 20
- **Deferred:** 2
- **Rejected:** 2
- **Blocking findings remaining:** 0
