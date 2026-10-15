---
title: GPU Lab Digital Twin — Solu-2 Epics and Stories
status: ready
module: 3
stepsCompleted: [requirements-extracted, epics-approved, stories-created, validated]
inputDocuments:
  - planning/prd.md
  - planning/ARCHITECTURE.md
  - planning/detailed-design/contracts.md
  - planning/detailed-design/ports-and-adapters.md
  - ux/DESIGN.md
  - ux/EXPERIENCE.md
  - test/test-design.md
---

# GPU Lab Digital Twin — Epics and Stories

## Overview

Four user-value epics implement the standalone simulated twin incrementally. Epic 1 is a walking skeleton through fixture, domain, persistence port, API, and Fleet Dashboard. Later epics depend only on earlier stories and never on future work. Physical GPU, DCGM, Prometheus, Kubernetes, reservation, scheduling, catalog, inference, and enterprise observability remain out of scope.

## Requirements Inventory

### Functional Requirements

FR-1 fixed 32-node/33-GPU inventory; FR-2 validated simulated ingestion; FR-3 ordered idempotent telemetry; FR-4 strict silent-node handling; FR-5 thermal protection; FR-6 reboot/state loss; FR-7 deterministic state evaluation; FR-8 maintenance lock/drain; FR-9 safe maintenance release; FR-10 flapping containment; FR-11 fleet/node views; FR-12 explainability; FR-13 fault simulation.

### Non-Functional Requirements

NFR-1 fleet completeness; NFR-2 hardware independence; NFR-3 thermal safety; NFR-4 silence accuracy; NFR-5 idempotency; NFR-6 determinism; NFR-7 explainability; NFR-8 flapping containment; NFR-9 data integrity; NFR-10 mandatory scenario coverage; NFR-11 atomic exposure ordering; NFR-12 process-local baseline/non-claims; NFR-13 precedence collision coverage.

### Architecture and UX Requirements

- AD-1 through AD-8 remain binding; all time is injected and all inputs simulated.
- Fleet summary, cards, alerts, and details use one complete fleet version and retain the prior version during refresh.
- Loading, Empty, Error, Success, and Denied states are represented by primitive DTO/error contracts; missing/stale values are never shown as zero/current.
- `ONLINE` is connectivity, not NodeState. Raw flapping evidence does not animate or oscillate the public card while ODD-5 is unresolved.
- Maintenance UI shows count/IDs/timestamp, not ETA or percent, and offers no terminate/checkpoint/schedule action.

## FR Coverage Map

| Requirement | Stories |
|---|---|
| FR-1 | 1.1 |
| FR-2 | 1.1, 1.2 |
| FR-3 | 1.2 |
| FR-4 | 1.3 |
| FR-5 | 2.1 |
| FR-6 | 2.2 |
| FR-7 | 1.3, 2.1, 2.2, 2.3, 3.1, 3.3 |
| FR-8 | 3.1, 3.2 |
| FR-9 | 3.3 |
| FR-10 | 2.3 |
| FR-11 | 1.1, 4.1 |
| FR-12 | 4.1 |
| FR-13 | 4.2 |

## Value Delivery Map

### Epic 1 — Live Fleet Awareness

Carlos and Alex can open a complete simulated 32-machine fleet, ingest current telemetry end to end, and distinguish fresh from silent nodes without physical hardware.

### Epic 2 — Automated Node Protection and Recovery

Carlos and Alex receive stable, explainable protection for heat, reboot/state loss, and connectivity flapping.

### Epic 3 — Maintenance and Operational Control

Carlos can cordon and drain a node using read-only mocked workload facts, handle conflicts safely, and release maintenance without bypassing health.

### Epic 4 — Explainable Operations and Fault Confidence

Carlos and Alex can inspect causal decisions and exercise all mandatory simulated faults with coherent UI states and verifiable isolation.

## Epic 1: Live Fleet Awareness

### Story 1.1: See the complete simulated fleet

**Protagonist:** Carlos and Alex

**User Story:** As Carlos or Alex, I want one complete fleet view fed by a simulated heartbeat happy path, so that I can trust the standalone twin without physical GPU dependencies.

**Traceability:** FR-1, FR-2, FR-11; NFR-1, NFR-2, NFR-11, NFR-12; UX Scenario 1; AD-1, AD-4, AD-8; ingest Q/I-H1/I-H6; HB-FRESH-001; SC-ISOLATION-001.

**Binding Invariants:** exactly 31 one-GPU 24 GB workstations plus one two-GPU 48 GB server; 32 nodes/33 GPUs/840 GB; state/cordon/explanation commit before fleet-version exposure; simulated hardware only.

**Files / expected implementation locations:** `domain/node_state.py`, `ports/in/heartbeat.py`, `ports/out/node_repository.py`, `adapters/sim/simulated_telemetry.py`, `api/routes/telemetry.py`, Fleet Dashboard surface.

**Schema / DTO / Event / OpenAPI references:** `nodes`, `gpu_devices`; `IngestHeartbeatRequest/Response`; `HeartbeatReceived`, `HeartbeatApplied`; `POST /v1/nodes/{nodeId}/heartbeats`.

**Dependencies:** none.

**Given / When / Then — happy path:** Given the canonical seed fleet in `HEALTHY`, when one fresh valid simulated heartbeat is ingested and the complete fleet version is exposed, then every node appears once, the target remains/enters `HEALTHY`, and its current evidence is visible.

**Given / When / Then — failure path:** Given an invalid GPU identifier or unknown node, when ingestion is attempted, then a typed 404/422 error is returned, no node mutates, and the UI shows Error/Denied rather than a partial fleet version.

**Definition of Done:** HB-FRESH-001 and SC-ISOLATION-001 are green; canonical cardinality assertions pass; Loading/Empty/Error/Success/Denied DTO handling is demonstrated; zero physical/adjacent-module calls.

### Story 1.2: Keep telemetry ordered and exactly-once

**Protagonist:** Carlos

**User Story:** As Carlos, I want duplicate and stale heartbeats contained, so that the live twin cannot roll backward or repeat operational history.

**Traceability:** FR-2, FR-3; NFR-5, NFR-9, NFR-11; UX Scenario 1; AD-1, AD-6; ingest P-H6/P-H7 and I-H1/I-H2/I-H5; HB-ORDER-001, HB-IDEM-001.

**Binding Invariants:** one event ID → one payload/outcome; stale telemetry cannot replace current; revision-conditional atomic commit; prior epoch cannot refill fields.

**Files / expected implementation locations:** `domain/heartbeat_policy.py`, `ports/out/node_repository.py`, `adapters/db/postgres_node_repository.py`, telemetry route.

**Schema / DTO / Event / OpenAPI references:** `telemetry_snapshots.event_id`, current/sequence indexes; heartbeat DTOs; disposition events; heartbeat 200/409 responses.

**Dependencies:** Story 1.1.

**Given / When / Then — happy path:** Given a current heartbeat, when the identical event is replayed 100 times, then the recorded duplicate response returns with one telemetry application and no duplicate history/audit/event/alert.

**Given / When / Then — failure path:** Given a newer accepted sample, when older or equal-ambiguous telemetry arrives, then it is late-ignored or rejected and current projection/revision stays unchanged.

**Definition of Done:** HB-ORDER-001 and HB-IDEM-001 green; SQL uniqueness/CAS integration tests green; no SELECT-then-UPDATE mutation.

### Story 1.3: Detect silence at the exact boundary

**Protagonist:** Carlos and Alex

**User Story:** As Carlos or Alex, I want silent machines shown safely and precisely, so that unavailable hardware is never advertised for new work.

**Traceability:** FR-4, FR-7; NFR-4, NFR-6; UX Scenario 4; AD-2, AD-4; transition P-T3/Q, I-H3/I-T1; HB-SILENCE-001.

**Binding Invariants:** equality at three intervals is not silent; strictly more than three is `OFFLINE` and cordoned; no first heartbeat remains `UNKNOWN`; fake time only.

**Files / expected implementation locations:** `domain/heartbeat_policy.py`, `domain/node_state.py`, `ports/out/clock.py`, `adapters/sim/fake_clock.py`.

**Schema / DTO / Event / OpenAPI references:** node last-receive fields; transition DTOs; `ClockEvaluated`, `NodeStateTransitioned`; state preview route.

**Dependencies:** Story 1.2.

**Given / When / Then — happy path:** Given a last accepted receive time, when FakeClock advances past `3×interval` and an ordered tick is evaluated, then the node is `OFFLINE`, cordoned, and explained.

**Given / When / Then — failure path:** Given exactly `3×interval`, when evaluated, then no early OFFLINE transition/history/alert occurs.

**Definition of Done:** HB-SILENCE-001 green; no wall-clock call/sleep; boundary property vectors pass.

## Epic 2: Automated Node Protection and Recovery

### Story 2.1: Cordon an overheating workstation

**Protagonist:** Carlos and Alex

**User Story:** As Carlos, I want `ws-gpu-14` automatically contained above 88°C, so that Alex cannot mistake unsafe hardware for eligible capacity.

**Traceability:** FR-5, FR-7; NFR-3, NFR-7, NFR-13; UX Scenario 2; AD-3, AD-4; ingest Q/I-H4 and transition I-T2/I-T3; HB-THERMAL-001, HB-THERMAL-002.

**Binding Invariants:** `>88` activates thermal reason; `88` does not; reason/state/cordon/explanation commit atomically; higher precedence retains reason.

**Files / expected implementation locations:** `domain/thermal_policy.py`, `domain/node_state.py`, node repository UoW, fleet/node views.

**Schema / DTO / Event / OpenAPI references:** GPU telemetry tables; ExplanationDTO; `NodeCordoned`, alert event; heartbeat route.

**Dependencies:** Story 1.3.

**Given / When / Then — happy path:** Given `ws-gpu-14` at 88.1°C, when accepted, then state is `DEGRADED`, cordoned is true, and explanation cites GPU/value/operator/88°C threshold/rule.

**Given / When / Then — failure path:** Given exactly 88.0°C, when accepted, then thermal alone creates no reason, cordon, or alert.

**Definition of Done:** both thermal RED tests green; non-eligible output precedes exposure; SQL/domain safety checks pass.

### Story 2.2: Explain workstation reboot recovery

**Protagonist:** Alex and Carlos

**User Story:** As Alex, I want `ws-gpu-05` shown as recovering after state loss, so that I understand why it remains unavailable.

**Traceability:** FR-6, FR-7; NFR-6, NFR-7, NFR-9; UX Scenario 3; AD-4, AD-6; ingest P-H3/I-H5 and transition I-T6; HB-REBOOT-001.

**Binding Invariants:** valid successor/marker increments epoch once; state is `RECOVERING` and cordoned; older epoch cannot refill; no direct OFFLINE→HEALTHY.

**Files / expected implementation locations:** `domain/heartbeat_policy.py`, `domain/node_state.py`, repository UoW, Node Detail.

**Schema / DTO / Event / OpenAPI references:** boot/evidence fields; heartbeat/explanation DTOs; `RebootDetected`, `NodeStateTransitioned`; heartbeat route.

**Dependencies:** Story 2.1.

**Given / When / Then — happy path:** Given boot A, when `ws-gpu-05` supplies boot B with succession/state-loss proof, then exactly one `RECOVERING` transition and explanation are committed.

**Given / When / Then — failure path:** Given boot B is current, when an A event replays, then it cannot mutate projection, restore ephemeral fields, or emit another reboot transition.

**Definition of Done:** HB-REBOOT-001 green; epoch/old-session integration tests green; unresolved ODD-3 safely holds recovery.

### Story 2.3: Contain five-second connectivity flapping

**Protagonist:** Carlos and Alex

**User Story:** As Carlos, I want five-second online/offline alternation contained without card oscillation or alert floods, so that the fleet remains readable while policy is unresolved.

**Traceability:** FR-10, FR-7; NFR-8, NFR-10; UX Scenario 4; AD-5; transition Q/I-T4/I-T5; ST-FLAP-001 (P0).

**Binding Invariants:** raw observations are evidence-only without ODD-5; public state/connectivity/cordon unchanged; zero flapping alerts; at most one current unresolved diagnostic; no hidden debounce.

**Files / expected implementation locations:** `domain/connectivity_policy.py`, `ports/out/stability_policy.py`, event/alert projector, Fleet Dashboard.

**Schema / DTO / Event / OpenAPI references:** alerts partial unique index; transition DTO; `ConnectivityObserved`, `PolicyDiagnosticUpserted`; transition preview route.

**Dependencies:** Story 2.2.

**Given / When / Then — happy path:** Given 12 alternating observations five seconds apart, when processed with ODD-5 unresolved, then every public tuple equals the stable baseline and explanation identifies `ERR_POLICY_UNRESOLVED`/ODD-5.

**Given / When / Then — failure path:** Given repeated raw changes, when projected, then no one-for-one transition and no `ERR_CONNECTIVITY_FLAPPING` alert is created; unresolved diagnostic count stays ≤1.

**Definition of Done:** ST-FLAP-001 green; no pulse/countdown; database alert uniqueness test green; P0 trace complete.

## Epic 3: Maintenance and Operational Control

### Story 3.1: Start a visible, non-destructive maintenance drain

**Protagonist:** Carlos and Alex

**User Story:** As Carlos, I want to lock and drain the central server while Alex sees active work context, so that maintenance begins safely without controlling workloads.

**Traceability:** FR-8, FR-7; NFR-7, NFR-11; UX Scenario 4 Maintenance; AD-4, AD-7, AD-8; maintenance Q/I-M2/I-M3/I-M5; MT-HAPPY-001, MT-EXPLAIN-001.

**Binding Invariants:** accepted lock and cordon are atomic; missing/stale/positive work means `DRAINING`; only fresh post-lock zero means `MAINTENANCE`; no work-control command.

**Files / expected implementation locations:** `domain/maintenance_policy.py`, maintenance inbound port/route, external context port/fixture, repository UoW, Maintenance Control.

**Schema / DTO / Event / OpenAPI references:** maintenance locks; request/response DTOs; `MaintenanceDrainRequested/Scheduled/Completed`; maintenance route.

**Dependencies:** Story 1.2.

**Given / When / Then — happy path:** Given active external/mock workloads, when Carlos schedules drain, then the node is immediately cordoned and `DRAINING`, with count/IDs/time visible and no ETA/percentage.

**Given / When / Then — failure path:** Given missing or stale workload evidence, when drain evaluates, then it remains `DRAINING` with `DRAIN_STATUS_UNKNOWN` and emits no terminate/checkpoint/place action.

**Definition of Done:** MT-HAPPY-001, MT-STALE-001, MT-EXPLAIN-001 green; mocked workload context remains read-only.

### Story 3.2: Reject duplicate and conflicting maintenance drains

**Protagonist:** Carlos

**User Story:** As Carlos, I want retries and concurrent maintenance conflicts resolved predictably, so that one node never gains duplicate locks or events.

**Traceability:** FR-8; NFR-5, NFR-9; UX maintenance Error/Outcome Unknown; AD-1, AD-7; maintenance P-M4–M6/I-M1; MT-CONC-001, MT-INVALID-001.

**Binding Invariants:** one active lock/node; one request payload/result; identical replay returns same lock; changed/conflicting request is typed and has zero mutation.

**Files / expected implementation locations:** maintenance application service/port, PostgreSQL repository, maintenance route/control reconciliation.

**Schema / DTO / Event / OpenAPI references:** maintenance unique indexes/request hash; ErrorBody; schedule event; 409/422 responses.

**Dependencies:** Story 3.1.

**Given / When / Then — happy path:** Given two simultaneous identical requests, when serialized, then one is scheduled, one is duplicate, and both return the same single lock with one event.

**Given / When / Then — failure path:** Given an empty reason, stale revision, or different active request, when submitted, then the typed error is returned and lock/projection/audit/event collections remain unchanged.

**Definition of Done:** MT-CONC-001 and MT-INVALID-001 green; partial unique index race test green; Outcome Unknown blocks retry until reconciliation.

### Story 3.3: Release maintenance without forgetting safety

**Protagonist:** Carlos and Alex

**User Story:** As Carlos, I want release to reevaluate all retained health evidence, so that maintenance completion never advertises an unsafe machine as healthy.

**Traceability:** FR-9, FR-7; NFR-6, NFR-13; UX Maintenance Success/Denied; AD-3, AD-4, AD-7; transition I-T1/I-T2 and maintenance I-M4; ST-PRECEDENCE-001.

**Binding Invariants:** release removes lock and invokes full reducer in one UoW; it never writes HEALTHY directly; thermal/silence/recovery evidence survives maintenance.

**Files / expected implementation locations:** `domain/maintenance_policy.py`, `domain/node_state.py`, repository UoW, Maintenance Control.

**Schema / DTO / Event / OpenAPI references:** lock release columns; ExplanationDTO/ErrorBody; state transition/audit events; internal transition contract.

**Dependencies:** Story 3.2.

**Given / When / Then — happy path:** Given a lock and fresh zero workload snapshot with no health reason, when release is accepted, then the reducer selects the evidence-supported state atomically.

**Given / When / Then — failure path:** Given active thermal or silence evidence, when released, then the node remains cordoned in the precedence-selected unsafe state and explanation retains the reason.

**Definition of Done:** ST-PRECEDENCE-001 and release collision matrix green; no false intermediate UNKNOWN/HEALTHY publication.

## Epic 4: Explainable Operations and Fault Confidence

### Story 4.1: Inspect causal decisions in every UI state

**Protagonist:** Carlos and Alex

**User Story:** As Carlos or Alex, I want structured reasons for every automatic decision and rejection, so that Loading, Empty, Error, Success, and Denied states remain actionable.

**Traceability:** FR-11, FR-12; NFR-7, NFR-11; UX all scenarios/states; AD-3, AD-4, AD-5, AD-6, AD-7; all Q/I-T3; ST-EXPLAIN-001 and operation explain tests.

**Binding Invariants:** every automated change/hold/rejection has rule IDs, observed values, threshold or expected state, evidence IDs, policy version, prior/result state; one fleet version is coherent.

**Files / expected implementation locations:** `domain/explanation.py`, event/audit projector, node/fleet query services, Fleet Dashboard and Node Detail.

**Schema / DTO / Event / OpenAPI references:** history/audit explanation JSON; ExplanationDTO/ErrorBody; all emitted decision events; all three routes.

**Dependencies:** Stories 2.3 and 3.3.

**Given / When / Then — happy path:** Given any mandatory automated decision, when Carlos opens Node Detail, then the rendered explanation exactly matches structured evidence used by the reducer.

**Given / When / Then — failure path:** Given required rule/evidence data is missing, when commit is attempted, then the transaction fails and no new fleet version is exposed.

**Definition of Done:** ST-EXPLAIN-001 plus thermal/reboot/maintenance explanation tests green; all UI states bind to DTO/error contracts; accessibility requirements pass.

### Story 4.2: Reproduce every mandatory fault safely

**Protagonist:** Carlos

**User Story:** As Carlos, I want deterministic fault scripts for heartbeat, thermal, reboot, maintenance, and flapping, so that I can demonstrate the twin safely.

**Traceability:** FR-13; NFR-2, NFR-10; UX Fault Injector plus Scenarios 1–4; AD-2, AD-3, AD-5, AD-6, AD-7, AD-8; operation Time clauses; HB/ST/MT mandatory tests.

**Binding Invariants:** scripts pass through normal inbound ports, use FakeClock, are repeatable, and cannot mutate projections directly or access hardware.

**Files / expected implementation locations:** `adapters/sim/simulated_telemetry.py`, `adapters/sim/fake_clock.py`, fault-injection driving adapter/UI.

**Schema / DTO / Event / OpenAPI references:** all request DTOs and ingested events; all three OpenAPI routes; no new schema.

**Dependencies:** Story 4.1.

**Given / When / Then — happy path:** Given the canonical fixture, when each mandatory script runs twice, then it emits the same ordered envelopes and produces the scenario's specified state/explanation.

**Given / When / Then — failure path:** Given a malformed script or nonconfigured node, when submitted, then typed validation fails without direct projection mutation or physical fallback.

**Definition of Done:** 4/4 mandatory scenarios and 1/1 edge case pass; no sleep/random/physical dependency; deterministic envelope comparison green.

### Story 4.3: Prove integrity and documented prototype limits

**Protagonist:** Carlos and Alex

**User Story:** As Carlos or Alex, I want the prototype to fail closed and state its limits, so that simulated results are trustworthy without production-capacity claims.

**Traceability:** FR-1, FR-3, FR-7; NFR-6, NFR-9, NFR-12, NFR-13; UX Error/Empty/Denied; AD-1, AD-4, AD-8; rejection non-effects and all invariants; SC-ISOLATION-001, ST-PRECEDENCE-001.

**Binding Invariants:** malformed/cross-node facts cannot corrupt current state; absent/stale never becomes zero/current; restart resets canonical fleet and labels history unavailable; precedence vectors are deterministic.

**Files / expected implementation locations:** domain policies, schema validators, query projections, prototype reset/session presentation.

**Schema / DTO / Event / OpenAPI references:** all SQL integrity constraints; ErrorBody; AuditRecorded; typed error responses.

**Dependencies:** Story 4.2.

**Given / When / Then — happy path:** Given the canonical run, when repeated precedence and restart vectors execute, then one output tuple results per vector and restart restores exactly 32 canonical projections with prior history unavailable.

**Given / When / Then — failure path:** Given malformed, unknown, cross-node, stale, or missing facts, when evaluated, then typed rejection/hold occurs and no value is fabricated or advertised as current.

**Definition of Done:** NFR-6/9/12/13 planned evidence becomes evidenced; schema/API/domain checks pass; no infinite-retention, durability, throughput, or latency claim.
