---
title: GPU Lab Digital Twin — Module 3 PRD
status: final
created: 2026-09-26
updated: 2026-09-26
module: 3
tier: Intermediate
---

# PRD: GPU Lab Digital Twin

## 1. Product and module purpose

The GPU Lab Digital Twin is a standalone, hardware-agnostic representation of the live operational state of the university's 32-machine GPU fleet. It converts simulated telemetry and mocked operational inputs into deterministic node states, eligibility signals, alerts, and human-readable explanations. Carlos uses it to find, isolate, recover, and maintain lab hardware; Alex uses it to understand whether a machine is safe and eligible for new work.

This PRD is strictly for Module 3. It defines what the twin owns and what adjacent platform modules must mock or consume. It does not select an implementation architecture, database, telemetry transport, or final visual design.

## 2. Problem statement

Physical lab machines fail, overheat, reboot, and disconnect. Without one authoritative live representation, Carlos cannot distinguish a transient telemetry gap from a failed node or safely prepare hardware for maintenance, and Alex cannot tell why a machine is unavailable. The module must maintain coherent state for 31 single-GPU workstations and one dual-GPU server while preventing unsafe placement signals, unstable state oscillation, and repeated alerts during connectivity flapping.

## 3. Named protagonists

- **Carlos — Hardware Lab Technician.** Monitors the fleet, investigates degraded and silent nodes, schedules maintenance, observes graceful drain progress, and decides when a maintained node may return.
- **Alex — Graduate Researcher.** Reads node availability, capacity, active reservation context, and cited reasons when a node is not eligible for new work. Alex does not schedule jobs or create reservations through this module.

### 3.1 Protagonist journeys

- **UJ-1 — Carlos detects and contains overheating.** Carlos sees `ws-gpu-14` cross 88°C, observes its transition to `DEGRADED`, confirms it is cordoned from new work, and reads the triggering temperature and rule in the decision explanation.
- **UJ-2 — Alex understands recovery.** After `ws-gpu-05` reboots, Alex sees `RECOVERING`, its last heartbeat and state-loss evidence, and that the node is not eligible for new work until recovery evidence satisfies the configured recovery policy.
- **UJ-3 — Carlos drains the server for maintenance.** Carlos places the dual-GPU server under a maintenance lock, watches mocked active workloads drain, and sees the node enter `MAINTENANCE` only after reported active workload count reaches zero.
- **UJ-4 — Carlos investigates a silent or flapping node.** Carlos sees missed-heartbeat evidence, a stable externally visible state instead of five-second oscillation, and bounded alert episodes rather than one alert per transition.

## 4. Module boundaries

### 4.1 Owned by Module 3

- Canonical in-memory or persisted twin record for exactly 32 configured physical machines: 31 workstations with one 24 GB GPU each and one server with two 48 GB GPUs.
- Validation and ingestion of simulated node heartbeats.
- Latest observed VRAM occupancy, GPU temperature, driver health, storage free space, active reservation snapshot, maintenance lock, boot/session identity, and heartbeat time.
- Deterministic node health/state derivation and transition history.
- Detection of silence after more than three expected heartbeat intervals.
- Safety cordon eligibility for new work, including mandatory thermal cordon above 88°C.
- Reboot/state-loss recognition and recovery representation.
- Maintenance lock and graceful drain state orchestration using mocked workload state.
- Flapping suppression and alert episode deduplication, with unresolved timing policy kept explicit.
- Explainable state and cordon decisions.
- Interactive Fleet Map / Grid Dashboard and simulated telemetry/fault injection inputs as the standalone prototype boundary.

### 4.2 Inputs mocked or delegated

- **Reservations:** read-only mocked external state; Module 3 displays active reservation references but does not create, conflict-check, allocate, expire, or cancel reservations (Module 4 boundary).
- **Workloads/jobs:** mocked identifiers and counts used to show drain progress; acceptance, placement, queuing, preemption, checkpointing, and scheduling are delegated (Modules 9 and 10 boundaries).
- **Observability aggregation:** Module 3 presents its own operational Fleet Map and node explanations; cross-service metrics, long-horizon reporting, token/latency dashboards, and enterprise alert aggregation are excluded (Module 11 boundary).
- **Model distribution/storage planning:** free-space telemetry is represented, but cache eviction, downloads, placement optimization, and replication are delegated (Module 6 boundary).
- Identity, authorization, policy, quotas, inference routing, catalog, training planning, and copilot functions are external to Module 3.

## 5. In-scope capabilities

1. Register the fixed simulated fleet inventory and expose its latest twin state.
2. Ingest, validate, order, and apply periodic simulated heartbeat samples.
3. Detect silence, over-temperature conditions, unhealthy drivers, reboots, maintenance activity, and recovery evidence.
4. Derive one deterministic node state plus an independent `cordoned` eligibility flag.
5. Operate maintenance drain against mocked active-workload state without implementing a scheduler.
6. Suppress externally visible flapping and deduplicate alerts into bounded episodes.
7. Explain every automated state transition and cordon decision with evidence and rule identifiers.
8. Provide a Fleet Map / Grid Dashboard plus fault generator for all mandatory scenarios.

## 6. Explicit non-goals

- Building or integrating the GPU Reservation System (Module 4).
- Building cache eviction or model distribution planning (Module 6).
- Building a night scheduler, training queue, placement engine, or job lifecycle controller (Modules 9 and 10).
- Building the cross-platform AI Infrastructure Observability Console, long-term analytics, executive reports, or token/latency monitoring (Module 11).
- Integrating with another student team's module, database, API, or Kubernetes cluster.
- Requiring CUDA, NVIDIA drivers, NVML, a physical NVIDIA GPU, or vendor-specific hardware access.
- Performing physical reboot, fan control, power cycling, job termination, checkpointing, or destructive remediation.
- Choosing the final transport, framework, datastore, deployment topology, or UI design in Phase 1.

## 7. Assumptions and open design decisions

### 7.1 Confirmed assumptions

- The authoritative inventory contains exactly 32 machines and 33 GPUs.
- Heartbeats, reservations, maintenance commands, and workload summaries are simulated or mocked.
- Each node has a configured heartbeat interval; silence is detected only after more than three complete configured intervals without an accepted heartbeat.
- The thermal anomaly condition is strictly `temperature > 88°C`; a reading equal to 88°C does not trigger that rule.
- A new boot/session identifier or an equivalent explicit state-loss marker is available in simulated telemetry to make reboot detection deterministic.
- State and eligibility are distinct: a node has one state and a separate `cordoned` flag.

### 7.2 OPEN DESIGN DECISIONS

- **ODD-1 — Heartbeat interval duration.** The official sources define “more than 3 intervals,” not the duration of one interval. Configuration must supply the duration; Phase 1 does not choose it.
- **ODD-2 — Out-of-order acceptance window and duplicate retention period.** Required to define late-message behavior; no values are given.
- **ODD-3 — Recovery evidence.** The number of consecutive healthy heartbeats and any minimum recovery duration required to leave `RECOVERING` are not specified.
- **ODD-4 — Thermal release policy.** The temperature below which thermal degradation may clear, the number of qualifying samples, and whether Carlos must acknowledge the condition are not specified.
- **ODD-5 — Flapping stabilization/debounce policy.** The mandatory case alternates every 5 seconds, but the stable-window duration, transition-count window, and clear criteria are not specified. No value is silently selected.
- **ODD-6 — Alert episode repeat interval and delivery destination.** Alert flooding must be prevented, but reminder cadence and external notification integration are not specified.
- **ODD-7 — Maintenance drain timeout and failure policy.** No deadline or forced-termination authority is assigned to Module 3. Until decided, the twin remains `DRAINING` and reports blocked progress; it never kills work.
- **ODD-8 — Driver-health vocabulary and low-storage thresholds.** Accepted driver status codes and any low-storage health threshold are not supplied. They remain configurable inputs and cannot be used to invent automatic failure boundaries. Until a supplied driver value has an approved health mapping, it cannot yield `HEALTHY`; evaluation holds the node cordoned with `ERR_POLICY_UNRESOLVED`.

## 8. Functional requirements

### FR-1 — Fixed fleet inventory

- **Responsibility:** Maintain the authoritative simulated inventory of Module 3 nodes and GPU capacity.
- **Trigger:** Prototype initialization or inventory reset.
- **Inputs:** Configured node IDs, node class, GPU count, per-GPU VRAM capacity, simulated storage capacity, and expected heartbeat interval.
- **Validation rules:** Node IDs must be unique; inventory must contain 31 workstation records with one 24 GB GPU and 500 GB NVMe storage each, and one server record with two 48 GB GPUs and 4 TB NVMe storage; each heartbeat interval must be positive; hardware access is not permitted.
- **Outputs:** Inventory of 32 node twins and 33 GPU device records, each initially `UNKNOWN` and cordoned until an accepted heartbeat establishes live state.
- **Measurable testable condition:** A canonical fixture produces exactly 32 node records, exactly 33 GPU records, aggregate VRAM capacity of 840 GB, workstation storage capacity of 500 GB per node, server storage capacity of 4 TB, and zero calls to a physical GPU API.

### FR-2 — Heartbeat validation and ingestion

- **Responsibility:** Accept valid simulated heartbeats and reject malformed or unknown-node samples without corrupting the current twin.
- **Trigger:** Receipt of a simulated heartbeat.
- **Inputs:** Node ID, event time, receive time, boot/session ID or state-loss marker, per-GPU VRAM occupied and temperature, driver health, storage free space, mocked reservation references, mocked active workload summary, and maintenance-lock observation.
- **Validation rules:** Node must exist; all required fields must be present; numeric values must be finite and non-negative; occupied VRAM must not exceed configured capacity; storage free space must not exceed configured storage capacity when capacity is supplied; temperature must use °C; enumeration values must be recognized; invalid samples must not replace last-known-good data.
- **Outputs:** Accepted heartbeat with ingestion result, or structured rejection containing field, supplied value, and violated rule.
- **Measurable testable condition:** A test set containing one valid sample and one sample for each validation rule updates the twin only for the valid sample and returns one cited rejection per invalid sample.

### FR-3 — Ordered, idempotent telemetry application

- **Responsibility:** Ensure duplicates and out-of-order heartbeats cannot roll a node back or create duplicate transitions and alerts.
- **Trigger:** A heartbeat passes FR-2 validation.
- **Inputs:** Node ID, boot/session ID, event time, receive time, and payload fingerprint or sequence identity.
- **Validation rules:** An exact duplicate is idempotently acknowledged; an event older than the latest accepted event for the same boot/session is classified late and cannot overwrite current state; a changed boot/session ID is evaluated by FR-6 rather than discarded as stale; ODD-2 governs the eventual retention/window value.
- **Outputs:** `APPLIED`, `DUPLICATE`, `LATE_IGNORED`, or `BOOT_CHANGE_DETECTED`, with current state unchanged for duplicate and late samples.
- **Measurable testable condition:** Replaying the same valid heartbeat 100 times produces one telemetry application, no more than one transition record, and no more than one alert episode.

### FR-4 — Silent-node detection

- **Responsibility:** Detect a node that has missed more than three configured heartbeat intervals and prevent it from receiving new work.
- **Trigger:** Evaluation at a heartbeat arrival or simulated clock advance.
- **Inputs:** Latest accepted receive time, evaluation time, and the node's configured heartbeat interval.
- **Validation rules:** Silence is true only when `evaluation_time - latest_accepted_receive_time > 3 × heartbeat_interval`; equality does not qualify; a node with no first heartbeat remains `UNKNOWN`; stale/duplicate events cannot reset the silence clock.
- **Outputs:** Transition to `OFFLINE`, `cordoned=true`, a silent-node alert episode, and explanation containing the last receive time, interval, elapsed interval count, and rule ID.
- **Measurable testable condition:** At exactly three missed intervals the node is not transitioned by this rule; at any simulated time greater than three intervals it is `OFFLINE` and cordoned after the next deterministic evaluation.

### FR-5 — Thermal anomaly and automatic cordon

- **Responsibility:** Contain a node whose accepted GPU temperature exceeds 88°C.
- **Trigger:** Application of a valid heartbeat containing any GPU temperature above 88°C.
- **Inputs:** Node ID, GPU ID, accepted temperature, previous state, and current lock/drain conditions.
- **Validation rules:** The rule uses strict greater-than comparison; equality at 88°C is not anomalous; any GPU over threshold affects the whole node; maintenance precedence remains deterministic under §10.
- **Outputs:** Health reason `THERMAL_OVER_88`, `cordoned=true`, externally visible state `DEGRADED` unless a higher-precedence maintenance/offline state applies, one thermal alert episode, and explanation naming the GPU, value, threshold, and rule.
- **Measurable testable condition:** A `ws-gpu-14` sample of 88.1°C results in a cordon and thermal reason; samples of 88.0°C and below do not trigger this rule; zero new-work eligibility responses are positive while the thermal reason is active.

### FR-6 — Reboot/state-loss detection

- **Responsibility:** Represent a simulated workstation reboot without misclassifying the first post-reboot heartbeat as ordinary recovery.
- **Trigger:** An accepted heartbeat carries a boot/session ID different from the last accepted ID, or an explicit simulated state-loss marker.
- **Inputs:** Previous and current boot/session IDs, state-loss marker, timestamps, and latest health metrics.
- **Validation rules:** A boot/session change must be attributable to the same known node; replay from an older boot/session cannot cause a second reboot transition; recovery exit conditions are governed by ODD-3.
- **Outputs:** State `RECOVERING`, `cordoned=true`, reset of ephemeral telemetry fields that are invalid across a reboot, a transition record, and an explanation citing state-loss evidence.
- **Measurable testable condition:** Changing `ws-gpu-05` from boot ID `A` to `B` creates exactly one transition to `RECOVERING`; replaying an `A` sample creates no additional transition and cannot restore pre-reboot ephemeral state.

### FR-7 — Deterministic state evaluation

- **Responsibility:** Derive exactly one externally visible node state and an independent cordon value from accepted facts using the state model in §10.
- **Trigger:** Any accepted telemetry update, maintenance command, mocked workload update, or simulated clock evaluation.
- **Inputs:** Current state, freshness, maintenance lock, drain status, boot/session evidence, thermal status, driver health, and configured recovery/flapping policies.
- **Validation rules:** Evaluate transition precedence in the fixed order defined in §10; all evaluated inputs must come from accepted current facts; unresolved ODD values must be supplied as configuration before the relevant exit transition is enabled; a driver value without an approved health mapping selects/retains a safe cordoned state under `ERR_POLICY_UNRESOLVED` and cannot yield `HEALTHY`.
- **Outputs:** Current state, cordon value, reason codes, transition record if changed, and decision explanation whether changed or held.
- **Measurable testable condition:** For every row in the state transition table, repeated evaluation of identical inputs produces an identical state, cordon value, reason-code set, and explanation rule ID.

### FR-8 — Maintenance lock and graceful drain

- **Responsibility:** Let Carlos prepare a node for maintenance without accepting new work or terminating mocked active work.
- **Trigger:** Carlos activates a maintenance lock for a known node, including the dual-GPU server.
- **Inputs:** Node ID, lock status, Carlos's maintenance reason, mocked active workload IDs/count, and subsequent workload summaries.
- **Validation rules:** Node must exist; reason must be non-empty; setting the lock immediately cordons the node; Carlos's Module 3 maintenance command record is authoritative; conflicting heartbeat lock observations produce `ERR_LOCK_SOURCE_MISMATCH` and cannot clear the command record; the twin cannot issue kill, checkpoint, preemption, or placement commands; drain completion requires mocked active workload count equal to zero; ODD-7 governs timeout policy.
- **Outputs:** `DRAINING` while active workload count is above zero; `MAINTENANCE` when it reaches zero; drain progress listing mocked workload references; explanation for every hold or transition.
- **Measurable testable condition:** With two mocked active workloads, locking the server yields `DRAINING` and `cordoned=true`; after reports move from two to one to zero, it transitions once to `MAINTENANCE`; no workload termination command is emitted.

### FR-9 — Maintenance release

- **Responsibility:** Remove a maintenance lock without bypassing health and recovery checks.
- **Trigger:** Carlos releases a maintenance lock.
- **Inputs:** Node ID, lock status, latest accepted heartbeat, boot/session evidence, active health reasons, and recovery policy configuration.
- **Validation rules:** Node must exist and be locked; release does not imply `HEALTHY`; an offline, thermal, unhealthy-driver, flapping, or recovery condition keeps the node cordoned and selects the applicable state by §10.
- **Outputs:** Lock removed, state reevaluated, cordon retained or cleared by evidence, and an explanation listing any condition preventing return to `HEALTHY`.
- **Measurable testable condition:** Releasing a lock on a node whose latest accepted temperature is above 88°C never yields an eligible `HEALTHY` result and preserves `THERMAL_OVER_88` evidence.

### FR-10 — Flapping suppression and alert deduplication

- **Responsibility:** Prevent a node alternating online/offline every five seconds from oscillating its externally visible state or generating an alert per alternation.
- **Trigger:** Repeated connectivity evidence alternates between heartbeat-present and silence at five-second cadence.
- **Inputs:** Simulated `ConnectivityObservation` events, timestamps, current stable state, open alert episode, and configured ODD-5/ODD-6 values.
- **Validation rules:** Each observation contains a known node ID, `ONLINE` or `OFFLINE`, and observation time; raw observations are retained separately from Heartbeats; observations enter the same FR-7 state evaluation path and never mutate state directly; public state changes only after the configured stabilization rule is satisfied; while one `(node_id, CONNECTIVITY_FLAPPING)` episode is open, equivalent observations update that episode rather than create alerts; no default timing threshold may be assumed.
- **Outputs:** Stable public state, `cordoned=true` while flapping is active, reason `CONNECTIVITY_FLAPPING`, one evolving alert episode, raw observation history, and explanation naming the configured policy.
- **Measurable testable condition:** In a parameterized test using any approved ODD-5 policy, 12 alternating observations at five-second spacing produce no more than one open flapping alert episode and no externally visible transition for each observation; the test is blocked from product sign-off until ODD-5 and ODD-6 are approved.

### FR-11 — Fleet and node views

- **Responsibility:** Present the live twin in an interactive Fleet Map / Grid Dashboard without becoming the cross-platform observability console.
- **Trigger:** Carlos or Alex opens/refreshes the fleet or node detail view, or an accepted update is applied.
- **Inputs:** All 32 current node twins, state, cordon, capacity/occupancy, temperature, driver health, storage free space, reservation snapshot, maintenance lock, last heartbeat, alert episodes, and explanations.
- **Validation rules:** Every configured node appears exactly once; stale values are labeled with last accepted time; mocked reservation/workload fields are labeled external; `UNKNOWN`, `OFFLINE`, and missing values cannot be rendered as zero or healthy.
- **Outputs:** 32-card/grid fleet view, filters by state/reason, and a node detail view with current and last-known evidence.
- **Measurable testable condition:** The canonical fixture renders exactly 32 unique node cards; a silent node shows `OFFLINE`, cordoned status, and last-known timestamp; no token, quota, model, or executive-report panel is present.

### FR-12 — Simulated telemetry and fault generation

- **Responsibility:** Exercise every mandatory scenario without physical hardware or another module.
- **Trigger:** Operator selects a fixture/fault action or starts periodic simulated heartbeats.
- **Inputs:** Canonical 32-node fixture, simulated clock, selected node, heartbeat controls, temperature value, boot/session change, maintenance lock, mocked workload count, and five-second flapping pattern.
- **Validation rules:** Generated events must use the same validation path as any other heartbeat; scenario presets may not mutate twin state directly; physical GPU APIs and external module calls are prohibited.
- **Outputs:** Reproducible event stream for normal fleet, silence, `ws-gpu-14 > 88°C`, `ws-gpu-05` reboot, server drain, and five-second flapping.
- **Measurable testable condition:** A clean run of six presets reproduces all four mandatory scenarios plus the normal and flapping cases using zero physical GPU dependencies and zero network calls to another student module.

### FR-13 — Decision explanations and audit history

- **Responsibility:** Make every automated state, cordon, hold, and rejection decision inspectable by Carlos and Alex.
- **Trigger:** FR-2 rejects input, FR-4 through FR-10 evaluates state, or a viewer requests decision history.
- **Inputs:** Rule ID/version, accepted evidence references, prior and resulting state, cordon change, event and evaluation times, and unresolved/selected policy values.
- **Validation rules:** Explanation must cite facts actually used; it must distinguish observed facts from mocked external state and configuration; secrets or personal data are not part of this module's telemetry contract.
- **Outputs:** Human-readable summary plus structured decision record containing rule, immutable telemetry/observation version IDs, exact evaluated evidence fields, prior state, result, and timestamp.
- **Measurable testable condition:** 100% of state transitions, cordon changes, held transitions, and telemetry rejections in the mandatory scenario test suite have a non-empty rule ID and at least one cited evidence field; for every record, the set of cited evidence/version IDs equals the set captured by its evaluation trace.

## 9. Non-functional requirements

- **NFR-1 — Fleet completeness:** For the canonical fixture, every fleet snapshot contains exactly 32 unique node IDs and 33 unique GPU IDs; missing or duplicate inventory records fail validation.
- **NFR-2 — Hardware independence:** The complete mandatory test suite executes with 0 physical GPUs, 0 CUDA/NVML calls, and 0 dependencies on another student module.
- **NFR-3 — Thermal safety:** Across 100% of accepted test samples where any GPU temperature is greater than 88°C, new-work eligibility is false before the corresponding evaluation result is exposed; at 88°C, the thermal rule produces 0 cordons by itself.
- **NFR-4 — Silence boundary accuracy:** Across boundary tests at `3.0 × interval` and `>3.0 × interval`, the silent rule produces 0 early `OFFLINE` transitions and detects 100% of qualifying cases at the next deterministic evaluation.
- **NFR-5 — Idempotency:** Replaying any accepted heartbeat 100 times produces exactly 1 applied telemetry version and at most 1 matching transition and 1 matching open alert episode.
- **NFR-6 — Determinism:** Repeating each state-machine test vector 1,000 times yields 1 distinct output tuple `(state, cordoned, reason codes, rule ID)` per vector.
- **NFR-7 — Explainability coverage:** 100% of transition, cordon, hold, and rejection records contain a rule ID, prior/result state where applicable, event/evaluation times, and at least 1 immutable evidence/version ID; 0 records may use only free-form rationale, and 100% must cite exactly the evidence set recorded by the evaluation trace.
- **NFR-8 — Flapping containment:** For the mandatory 12-observation, five-second alternating sequence, the system creates at most 1 concurrently open `CONNECTIVITY_FLAPPING` alert episode and 0 one-for-one public state transitions. Passing product sign-off additionally requires approved numeric ODD-5 and ODD-6 configuration.
- **NFR-9 — Data integrity:** In the mandatory test suite, 0 malformed, unknown-node, duplicate, or late-ignored heartbeats overwrite last-known-good current telemetry.
- **NFR-10 — Prototype coverage:** Automated scenario tests must achieve 4 of 4 mandatory scenario passes and 1 of 1 mandatory edge-case pass before Phase 1 downstream handoff; any failed case blocks closure.
- **NFR-11 — Decision latency:** `OPEN DESIGN DECISION`: the maximum time from heartbeat receipt or simulated clock advance to exposed state/cordon result is not specified by the official sources. A numeric budget must be approved before implementation readiness; tests must then show at least 99% of evaluations within that budget over a declared sample size.
- **NFR-12 — Retention capacity:** `OPEN DESIGN DECISION`: the required history duration and maximum stored decision/telemetry records are unspecified. Numeric retention and capacity limits must be approved before implementation readiness; no infinite-retention claim is permitted.
- **NFR-13 — State-precedence collision coverage:** The state-machine suite must test 100% of the 10 transition-table rows, every pair among maintenance, silence, reboot/state loss, thermal anomaly, unhealthy driver, and flapping conditions, plus 1 all-at-once vector; every vector must assert state, cordon, retained reason codes, rule ID, and lock-release reevaluation result.

## 10. Domain entities

- **NodeTwin:** One configured physical machine; owns identity, class, expected heartbeat interval, current state, cordon flag, reasons, last-known telemetry, current boot/session, and maintenance lock.
- **GpuDeviceTwin:** One GPU belonging to one NodeTwin; configured VRAM capacity plus latest occupancy and temperature.
- **Heartbeat:** Immutable simulated observation submitted for one NodeTwin with event/receive times and boot/session evidence.
- **TelemetrySnapshot:** Last accepted current facts derived from a Heartbeat; never substitutes missing data with zero.
- **ReservationSnapshot:** Read-only mocked external references associated with a NodeTwin.
- **WorkloadSnapshot:** Read-only mocked active workload IDs/count used only for maintenance drain progress.
- **MaintenanceLock:** Carlos-directed lock with active status, reason, and timestamps.
- **StateTransition:** Immutable record of prior state, resulting state, trigger, rule ID, and evidence references.
- **AlertEpisode:** Deduplicated occurrence for a node and reason, with opened, last-observed, update-count, and closed fields.
- **ConnectivityObservation:** Immutable simulated `ONLINE`/`OFFLINE` observation for a known node and observation time, used only to exercise and explain connectivity stabilization; it cannot directly mutate state.
- **DecisionExplanation:** Structured and human-readable reason for a state, cordon, hold, or input rejection.
- **FaultScenario:** Reproducible simulated event sequence for prototype testing.

## 11. Deterministic node state model

### 11.1 States

- `UNKNOWN`: No accepted live heartbeat has established current state.
- `HEALTHY`: Current accepted evidence has no active condition requiring another state; eligibility also requires `cordoned=false`.
- `DEGRADED`: Current evidence contains a non-maintenance health reason such as thermal anomaly, unhealthy driver, or active flapping.
- `RECOVERING`: State loss/reboot was detected and approved recovery evidence has not yet been met.
- `DRAINING`: Maintenance lock is active and mocked active workload count is greater than zero.
- `MAINTENANCE`: Maintenance lock is active and mocked active workload count is zero.
- `OFFLINE`: More than three configured heartbeat intervals have elapsed since the latest accepted heartbeat.

### 11.2 State/cordon invariant

`UNKNOWN`, `DEGRADED`, `RECOVERING`, `DRAINING`, `MAINTENANCE`, and `OFFLINE` always imply `cordoned=true`. `HEALTHY` permits `cordoned=false` only when no independent safety reason remains. Cordon means “not eligible for new work”; it does not cancel, kill, place, or reschedule work.

### 11.3 Evaluation precedence

On each trigger, evaluate exactly in this order:

1. If the maintenance lock is active and mocked active workload count is greater than zero, select `DRAINING`.
2. Else if the maintenance lock is active and mocked active workload count is zero, select `MAINTENANCE`.
3. Else if silence is greater than three configured intervals, select `OFFLINE`.
4. Else if new boot/session or state-loss evidence exists and ODD-3 recovery evidence is not satisfied, select `RECOVERING`.
5. Else if any active thermal, driver, or flapping reason exists, select `DEGRADED`.
6. Else if at least one current accepted heartbeat exists, select `HEALTHY`.
7. Else select `UNKNOWN`.

Maintenance precedence preserves Carlos's declared operational lock even if health also deteriorates; all secondary reason codes remain visible and affect release. Offline evidence is retained during maintenance but does not erase the lock. This precedence selects representation only and never declares unhealthy hardware safe.

Each degradation reason has an independent lifecycle and approved clear rule. A node can leave `DEGRADED` only when every active reason has satisfied its own clear rule. If any required clear rule is absent or unresolved, `ERR_POLICY_UNRESOLVED` holds the node cordoned; clearing one reason never clears another.

### 11.4 Transition table

| Current state | Trigger/guard | Next state | Cordon | Deterministic action |
|---|---|---|---|---|
| Any | Maintenance lock active; active workloads > 0 | `DRAINING` | true | Retain health reasons; show mocked workload drain progress |
| Any | Maintenance lock active; active workloads = 0 | `MAINTENANCE` | true | Record drain completion; emit no termination command |
| Any unlocked | Silence > 3 configured intervals | `OFFLINE` | true | Open/update silent episode; retain last-known telemetry |
| Any unlocked/non-silent | New boot/session or state-loss evidence; recovery incomplete | `RECOVERING` | true | Reset invalid ephemeral fields; open recovery evidence set |
| Any unlocked/current | Temperature > 88°C, unhealthy driver, or active flapping | `DEGRADED` | true | Add reason and open/update matching alert episode |
| `RECOVERING` | ODD-3 recovery evidence satisfied; no degradation | `HEALTHY` | false | Record evidence used to clear recovery |
| `DEGRADED` | Every active reason's approved clear rule satisfied | `HEALTHY` | false | Close corresponding alert episodes |
| `OFFLINE` | Current heartbeat returns | `RECOVERING` | true | Require ODD-3 evidence; do not jump directly to `HEALTHY` |
| `MAINTENANCE`/`DRAINING` | Lock released | Reevaluate rows 3–7 | derived | Never bypass active safety/recovery reasons |
| `UNKNOWN` | First current valid heartbeat | `HEALTHY` or `DEGRADED` | derived | Apply current health evidence in same evaluation |

## 12. Telemetry model

Each simulated Heartbeat contains:

| Field | Required | Validation/meaning |
|---|---:|---|
| `node_id` | yes | Must match one configured NodeTwin |
| `event_time` | yes | Source observation time; finite timestamp |
| `receive_time` | yes | Twin receipt time; used for silence evaluation |
| `boot_session_id` or `state_loss_marker` | yes | Deterministic reboot/state-loss evidence |
| `gpu_samples[]` | yes | Exactly configured GPU count; unique GPU IDs |
| `gpu_samples[].vram_occupied_gb` | yes | Finite, `0 <= value <= configured capacity` |
| `gpu_samples[].temperature_c` | yes | Finite °C value; `>88` activates thermal reason |
| `driver_health` | yes | Recognized configured enum; vocabulary is ODD-8 |
| `storage_free_gb` | yes | Finite and non-negative; bounded by capacity when supplied |
| `reservation_refs[]` | yes | Mocked external read-only identifiers; empty allowed |
| `active_workload_refs[]` | yes | Mocked external identifiers used for drain display only |
| `maintenance_lock_observed` | yes | Observation only; Carlos's command record remains authoritative |

The twin retains current accepted values, last-known values, freshness, and provenance. Missing, rejected, late, or unknown fields never become zero and never overwrite last-known-good values.

## 13. Error and failure model

| Code | Condition | State effect | Required response |
|---|---|---|---|
| `ERR_UNKNOWN_NODE` | Heartbeat node ID is not configured | none | Reject and cite node ID rule |
| `ERR_SCHEMA` | Required field/type/enum missing or invalid | none | Reject field; preserve current twin |
| `ERR_CAPACITY_RANGE` | VRAM/storage violates configured capacity | none | Reject sample; cite value and bound |
| `ERR_DUPLICATE` | Exact sample already applied | none | Idempotent acknowledgement; no new alert |
| `ERR_LATE_EVENT` | Older event for current/older boot session | none | Ignore for current state; preserve audit evidence |
| `ERR_SILENT` | Silence > 3 configured intervals | `OFFLINE` | Cordon; open/update one episode |
| `ERR_THERMAL_88` | Any accepted GPU temperature > 88°C | `DEGRADED` unless higher precedence | Cordon; identify GPU/value/rule |
| `ERR_DRIVER_UNHEALTHY` | Configured unhealthy driver status | `DEGRADED` unless higher precedence | Cordon; cite status |
| `ERR_STATE_LOSS` | New boot/session or explicit loss marker | `RECOVERING` unless higher precedence | Cordon; reset invalid ephemeral state |
| `ERR_DRAIN_BLOCKED` | Maintenance drain retains active mocked workloads | `DRAINING` | Report workload refs; never force terminate |
| `ERR_CONNECTIVITY_FLAPPING` | Approved ODD-5 policy detects five-second alternation | `DEGRADED` unless higher precedence | Cordon; update one episode, suppress oscillation |
| `ERR_LOCK_SOURCE_MISMATCH` | Heartbeat lock observation conflicts with Carlos's command record | no automatic lock change | Keep command record authoritative; surface mismatch |
| `ERR_POLICY_UNRESOLVED` | Required ODD configuration absent | hold current safe state | Keep cordoned; explain which decision is unresolved |

An AlertEpisode is uniquely open per `(node_id, reason_code)`. Equivalent observations update its `last_observed` and `update_count`. It closes only when that reason's approved clear rule is satisfied; a later recurrence creates a new episode rather than reopening or merging with the closed incident.

## 14. Explainability requirements

Every automated decision must expose:

1. Node ID and decision time.
2. Prior state/cordon and resulting state/cordon.
3. Stable rule ID and rule version.
4. Trigger and accepted evidence fields actually evaluated, with event and receive times.
5. Threshold/configuration used and whether it is authoritative or an approved design value.
6. Human-readable reason suitable for Carlos and a concise availability explanation suitable for Alex.
7. Mock/external labels on reservation and workload evidence.
8. Hold reason when an ODD is unresolved; the system must not fabricate a policy value.
9. Immutable evidence/version identifiers matching the exact evaluation trace, so the decision can be reproduced from the cited inputs.

Example: “`ws-gpu-14` was cordoned and represented as `DEGRADED` because GPU 0 reported 88.1°C at 14:05:03, exceeding the authoritative `>88°C` rule (`ERR_THERMAL_88`). No new-work eligibility is advertised.”

## 15. Mandatory scenario traceability

| Mandatory scenario | Protagonist coverage | Functional requirements | Verifiable outcome |
|---|---|---|---|
| 1. Fleet Heartbeat Ingestion | Carlos monitors; Alex reads availability | FR-1, FR-2, FR-3, FR-4, FR-7, FR-11, FR-12, FR-13 | All 32 nodes ingest simulated samples; silence only after >3 intervals; silent nodes are cordoned and explained |
| 2. Thermal Anomaly & Automatic Cordon | Carlos contains `ws-gpu-14`; Alex sees why unavailable | FR-2, FR-5, FR-7, FR-11, FR-12, FR-13 | 88.1°C yields `DEGRADED` and cordoned; 88.0°C does not trigger the thermal rule |
| 3. Simulated Workstation Reboot | Alex sees recovery; Carlos sees state-loss evidence | FR-3, FR-6, FR-7, FR-11, FR-12, FR-13 | Boot/session change on `ws-gpu-05` yields exactly one `RECOVERING` transition and remains cordoned pending ODD-3 evidence |
| 4. Maintenance Drain | Carlos locks/drains the dual-GPU server; Alex sees unavailability reason | FR-7, FR-8, FR-9, FR-11, FR-12, FR-13 | Lock with active work yields `DRAINING`; zero mocked active workloads yields `MAINTENANCE`; no scheduler/kill action occurs |
| Mandatory flapping edge case | Carlos investigates stable representation and bounded alerts; Alex avoids misleading oscillation | FR-3, FR-7, FR-10, FR-11, FR-12, FR-13 | Five-second alternation is cordoned, does not map one-for-one to public state transitions, and opens at most one concurrent episode under approved ODD-5/6 policy |

## 16. Phase 1 closure conditions

- Both authoritative PDFs are present and reflected in this PRD.
- All four mandatory scenarios map to testable FRs.
- The mandatory flapping case is specified without inventing a debounce duration.
- Every adversarial-review finding is triaged; all accepted findings are incorporated.
- No unresolved finding permits unsafe thermal behavior, silent-node eligibility, state oscillation, alert flooding, or scope leakage.
- ODD-1 through ODD-8 remain explicit inputs for later human decisions; any ODD that blocks safe implementation must be resolved before implementation-readiness sign-off, not silently defaulted.
