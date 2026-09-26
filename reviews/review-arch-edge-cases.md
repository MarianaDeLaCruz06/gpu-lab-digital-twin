# Architecture Review — Edge-Case-Hunter Lens

Date: 2026-09-26  
Artifact: `planning/ARCHITECTURE.md` initial Phase 3 draft  
Lens: BMad `edge-case-hunter`

## Verdict

Ten unhandled boundary paths were traced in the initial draft. Seven are accepted and applied, two are deferred to existing capacity/retention decisions, and one is rejected as a physical-hardware scope violation. Accepted fixes close the command, stale snapshot, inventory, event-validation, and alert-lifecycle paths.

## Findings

### ARCH-EDGE-01

- **Severity:** HIGH
- **Issue:** A workload snapshot can be received after lock acquisition while carrying observations taken before the lock.
- **Recommendation:** Require both `observed_at >= lock.acquired_at` and `received_at >= lock.acquired_at` before zero can complete drain.
- **Classification:** **ACCEPT**
- **Rationale:** Receive time alone does not prove the zero-workload fact is post-lock.

### ARCH-EDGE-02

- **Severity:** HIGH
- **Issue:** Maintenance commands appear able to mutate LockStore outside the per-node event queue.
- **Recommendation:** Represent lock/release as node events; only Node Event Processor commits LockStore and projection together.
- **Classification:** **ACCEPT**
- **Rationale:** Direct service mutation could race heartbeat or workload reduction.

### ARCH-EDGE-03

- **Severity:** MEDIUM
- **Issue:** Equal-time Clock Ticks with different event IDs have no declared outcome.
- **Recommendation:** Require strictly increasing simulated time; identical event replay is idempotent, all other equal/backward ticks reject.
- **Classification:** **ACCEPT**
- **Rationale:** Duplicate evaluation events must not create divergent ingest history.

### ARCH-EDGE-04

- **Severity:** HIGH
- **Issue:** Inventory mutation during a run has no guard.
- **Recommendation:** Freeze Node/GPU topology and capacities for the run; require reset/new run to change inventory.
- **Classification:** **ACCEPT**
- **Rationale:** Mid-run ownership/cardinality changes invalidate projections and evidence.

### ARCH-EDGE-05

- **Severity:** HIGH
- **Issue:** External context can arrive out of source order without an explicit stale rule for reservations.
- **Recommendation:** Require source revision/time on both ReservationContext and WorkloadSnapshot and ignore non-increasing revisions.
- **Classification:** **ACCEPT**
- **Rationale:** Older external facts must not replace current read-only context.

### ARCH-EDGE-06

- **Severity:** HIGH
- **Issue:** A multi-GPU heartbeat can partially validate and apply one GPU before another fails.
- **Recommendation:** Validate exact membership and all samples before appending/applying any part of the Heartbeat.
- **Classification:** **ACCEPT**
- **Rationale:** The dual-GPU server must not expose a half-updated TelemetrySnapshot.

### ARCH-EDGE-07

- **Severity:** MEDIUM
- **Issue:** An alert reason closes and reactivates while a closed episode retains the same key.
- **Recommendation:** Keep one open episode per key; recurrence after closure creates a new immutable episode ID.
- **Classification:** **ACCEPT**
- **Rationale:** This preserves distinct incidents while preventing simultaneous duplicates.

### ARCH-EDGE-08

- **Severity:** MEDIUM
- **Issue:** An event replay after idempotency retention expires can be applied again.
- **Recommendation:** Set retention at least as long as evidence replay horizon or reject events older than a configured floor.
- **Classification:** **DEFER**
- **Rationale:** ODD-2/NFR-12 must supply numeric retention; no safe value is authoritative yet.

### ARCH-EDGE-09

- **Severity:** MEDIUM
- **Issue:** Unbounded workload ID lists can exceed process memory or response capacity.
- **Recommendation:** Approve numeric fixture/list limits and reject oversized snapshots atomically.
- **Classification:** **DEFER**
- **Rationale:** NFR-12 capacity is unresolved; architecture records the needed validation without inventing the maximum.

### ARCH-EDGE-10

- **Severity:** HIGH
- **Issue:** A reviewer proposes reading NVML when simulated telemetry is absent.
- **Recommendation:** Add a physical-GPU fallback adapter for missing samples.
- **Classification:** **REJECT**
- **Rationale:** Physical NVIDIA dependency is explicitly prohibited; missing telemetry must stay absent/last-known and fail closed.

## Independent verification findings

### ARCH-EDGE-11

- **Severity:** CRITICAL
- **Issue:** Active lock plus absent/stale workload evidence could select a non-maintenance state.
- **Recommendation:** Select `DRAINING` with `DRAIN_STATUS_UNKNOWN` for that branch.
- **Classification:** **ACCEPT**
- **Rationale:** Active maintenance must be total over positive, zero, and unknown workload evidence.

### ARCH-EDGE-12

- **Severity:** HIGH
- **Issue:** Older connectivity observation can arrive after a newer one.
- **Recommendation:** Apply per-node source sequence/event-time ordering before Stability Policy.
- **Classification:** **ACCEPT**
- **Rationale:** Stale raw evidence cannot corrupt classification or public connectivity.

### ARCH-EDGE-13

- **Severity:** CRITICAL
- **Issue:** Fleet query can occur while a Clock Tick is only partly processed.
- **Recommendation:** Publish only after all 32 node outcomes complete; serve prior version meanwhile.
- **Classification:** **ACCEPT**
- **Rationale:** Prevents mixed pre/post-tick silence decisions.

### ARCH-EDGE-14

- **Severity:** CRITICAL
- **Issue:** Explicit state-loss marker without a new boot ID can leave old-session events current.
- **Recommendation:** Increment a monotonic evidence epoch on every accepted marker and reject prior-epoch mutation.
- **Classification:** **ACCEPT**
- **Rationale:** Cleared reboot-ephemeral state must not be repopulated by older evidence.

## Counts

- **Total:** 14
- **Accepted:** 11
- **Deferred:** 2
- **Rejected:** 1
- **Blocking findings remaining:** 0

## Combined Phase 3 review totals

- **Total:** 38
- **Accepted:** 31
- **Deferred:** 4
- **Rejected:** 3
- **Blocking findings remaining:** 0
