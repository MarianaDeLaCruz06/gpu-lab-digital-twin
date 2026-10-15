# Module 3 Solu-2 Behavioral Contracts

Scope is the GPU Lab Digital Twin only. Names are camelCase at ingress/events and snake_case only inside SQL. All timestamps are timezone-aware RFC 3339 UTC instants. `NodeId` matches `^[a-z0-9][a-z0-9-]{0,62}$`; `EventId`, `RequestId`, and returned record IDs are UUIDs. Domain input types contain primitives, enums, and immutable value objects only.

The three operations below are the complete Solu-2 mutation surface. Authentication/RBAC is external; the local prototype supplies an actor label and never claims production authorization.

## 1. `ingestHeartbeat(nodeId, payload, at)`

### Operation

```text
async ingestHeartbeat(nodeId: NodeId, payload: HeartbeatPayload, at: UtcInstant) -> HeartbeatResponse
```

### Layer

Inbound Port. It validates and sequences input, then calls the core reducer through the node event processor. Persistence and event publication are outbound ports.

### Preconditions (P)

| P | Exact requirement | Failure |
|---|---|---|
| P-H1 | `nodeId` is non-null, matches `NodeId`, and exists in the immutable 32-node inventory. | malformed: `ERR_SCHEMA`/422; absent: `ERR_UNKNOWN_NODE`/404 |
| P-H2 | `payload.eventId` is a UUID; `schemaVersion="1.0"`; `occurredAt`, `receivedAt`, and `at` are non-null aware UTC instants; `at == payload.receivedAt`. | `ERR_SCHEMA`/422 |
| P-H3 | `bootSessionId` is 1–128 characters. `previousBootSessionId` is null unless declaring succession. `stateLoss` is Boolean. A changed boot ID requires `stateLoss=true` or `previousBootSessionId` equal to the current boot ID. | `ERR_BOOT_SUCCESSION`/409 |
| P-H4 | `sourceSequence` is null or integer `>=0`; GPU samples exactly match configured device IDs; temperatures are finite and `>=0`; occupied VRAM is finite and within device capacity; storage free is finite and within node capacity; driver health is `HEALTHY|UNHEALTHY|UNKNOWN`. | schema/type: `ERR_SCHEMA`/422; capacity: `ERR_CAPACITY_RANGE`/422 |
| P-H5 | External reservation/workload context is null or labeled `EXTERNAL_MOCK` with nonnegative `sourceRevision`, `observedAt`, and `receivedAt`; it is normalized through the External Context Port and is never owned by Module 3. | `ERR_SCHEMA`/422 |
| P-H6 | An existing `eventId` with the same canonical SHA-256 payload hash is an idempotent replay. The same ID with a different hash is forbidden. | identical: success/200 `DUPLICATE`; mismatch: `ERR_IDEMPOTENCY_CONFLICT`/409 |
| P-H7 | For the current boot epoch, a heartbeat older than latest accepted `occurredAt`, or with a non-increasing supplied sequence, cannot become current. A different payload at equal time without a higher sequence is ambiguous. | older: success/200 `LATE_IGNORED`; equal ambiguous: `ERR_ORDER_AMBIGUOUS`/409 |
| P-H8 | The local simulation boundary supplies actor `simulator` or `fault-injector`; external production authorization is not asserted. | `ERR_POLICY_STATE_CONFLICT`/409 if a non-local mutation context reaches the prototype port |

### Postconditions (Q)

On `APPLIED`, return exactly `HeartbeatResponse { eventId, nodeId, outcome, nodeRevision, state, cordoned, connectivityStatus, acceptedAt, explanation }`. The operation atomically persists the idempotency record, telemetry snapshot, node projection revision, zero-or-one state history row, affected alert/diagnostic row, audit event, and emitted domain events. Thermal evaluation uses strict `temperatureC > 88`; it activates `ERR_THERMAL_88`, forces `cordoned=true`, and selects `DEGRADED` unless maintenance, silence, or recovery has higher precedence. A valid successor boot or explicit state loss increments the evidence epoch, clears boot-ephemeral facts, and makes the `ws-gpu-05` scenario `RECOVERING` unless higher precedence applies. Explanation contains rule IDs, exact observed values, threshold/expected-state data, evidence IDs, policy version, and prior/result state.

Events are `HeartbeatApplied` plus, when applicable, one `NodeStateTransitioned`, `NodeCordoned`, `AlertEpisodeOpenedOrUpdated`, or `PolicyDiagnosticUpserted`; every event and audit row contains `eventId`, `occurredAt`, and `schemaVersion`.

For `DUPLICATE`, return the recorded response and create no telemetry, history, alert, audit, or event effect. For `LATE_IGNORED`, preserve current projection and last accepted receive time, append one audit/evidence disposition only once under its unique event ID, and return the current state. All rejected calls guarantee no node projection, lock, telemetry-current, history, alert, or domain-event mutation; a rejection audit may be written only atomically with its idempotency result.

### Invariants (I)

| ID | Deterministic invariant | AD-n | Enforcement point |
|---|---|---|---|
| I-H1 | One event ID identifies one canonical payload and one recorded outcome. | AD-1 | `telemetry_snapshots.event_id UNIQUE`, canonical hash check, idempotency port |
| I-H2 | Older/equal-ambiguous telemetry never overwrites a newer accepted snapshot. | AD-1, AD-6 | ordering guard plus revision-conditional repository write |
| I-H3 | Silence is true only when a first accepted heartbeat exists and `evaluationAt-lastAcceptedReceiveAt > 3*heartbeatInterval`; equality is false. | AD-2 | HeartbeatPolicy domain guard using injected time |
| I-H4 | Any accepted GPU reading `>88` atomically records the thermal reason, explanation, and `cordoned=true`; exactly 88 does not activate it. | AD-3, AD-4 | reducer plus transaction and SQL state/cordon check |
| I-H5 | A valid state-loss successor increments evidence epoch once and prior-epoch inputs cannot repopulate current fields. | AD-6 | boot succession guard and unique event/revision transaction |
| I-H6 | External/mock context remains labeled, versioned, read-only, and cannot be converted from absent/stale to zero/current. | AD-8 | External Context Port and DTO nullability |

### Concurrency / Idempotency

The sole global sequencer assigns `ingestOffset`; one processor serializes each node. The repository performs one conditional update `WHERE revision=:expectedRevision RETURNING *`; no SELECT-then-UPDATE mutation is permitted. A stale expected revision yields `ERR_REVISION_CONFLICT`/409 and the caller may retry. Exact duplicate IDs return the original response. Conflicting ID reuse returns 409. Out-of-order input is recorded once as `LATE_IGNORED`, never applied. Events for different nodes may proceed concurrently.

### Time

`at` is adapter-supplied receive time. Clock evaluation is a separate ordered signal into `transitionNodeState`; domain code never reads wall time. Heartbeat silence uses accepted receive time, strict greater-than, and the configured positive interval; ODD-1 remains configuration, not a hidden default.

### Latency budget

NFR-11 defines no numeric latency SLA. The binding budget is exposure ordering: state, cordon, alert, and explanation commit before the new fleet version becomes visible; implementation later records baseline latency.

## 2. `transitionNodeState(nodeId, signal)`

### Operation

```text
transitionNodeState(nodeId: NodeId, signal: NodeSignal) -> NodeTransitionResponse
```

`NodeSignal` is one of `HeartbeatAccepted(eventId)`, `ClockEvaluated(eventId,evaluationAt)`, `ConnectivityObserved(eventId,status,observedAt,receivedAt)`, `WorkloadSnapshotAccepted(eventId,snapshotId)`, or `MaintenanceCommandAccepted(requestId)`. This is a core operation invoked by application ports; it is not an independent public HTTP route.

### Layer

Core Domain. The public ingress route `/v1/nodes/{nodeId}/state-transitions:preview` exposes a side-effect-free evaluation of the same contract for red-phase verification; adapters cannot mutate state directly.

### Preconditions (P)

| P | Exact requirement | Failure |
|---|---|---|
| P-T1 | `nodeId` is valid and configured; `signal` is non-null and one closed-union member with valid referenced evidence. | `ERR_SCHEMA`/422 or `ERR_UNKNOWN_NODE`/404 |
| P-T2 | Referenced heartbeat/workload/maintenance evidence exists, belongs to the node, and is current/accepted. | `ERR_EVIDENCE_NOT_FOUND`/409 |
| P-T3 | `ClockEvaluated.evaluationAt` is strictly later than the last accepted distinct tick; exact same event replay is idempotent. | `ERR_CLOCK_ORDER`/409 |
| P-T4 | A requested state edge must exist in the architecture transition table and satisfy fixed precedence. | `ERR_INVALID_TRANSITION`/409 |
| P-T5 | Any exit requiring unresolved ODD-3/4/5/6 configuration is forbidden. | `ERR_POLICY_UNRESOLVED`/409 |

### Postconditions (Q)

Return exactly `NodeTransitionResponse { eventId, nodeId, outcome, nodeRevision, priorState, state, cordoned, connectivityStatus, activeReasonCodes, transitioned, explanation }`. The reducer consumes one immutable Fact Set and chooses exactly one public state in order: maintenance with unknown/stale/positive workload → `DRAINING`; maintenance with fresh post-lock zero → `MAINTENANCE`; strict silence → `OFFLINE`; state loss/recovery → `RECOVERING`; active thermal/driver/approved flapping → `DEGRADED`; current heartbeat/no reason → `HEALTHY`; otherwise `UNKNOWN`.

If state or cordon changes, atomically persist the new projection, one history row, explanation/audit, alert effects, and emitted `NodeStateTransitioned`/`NodeCordoned` events. If held, persist the explainable decision/audit without a history row. The explanation cites the complete evaluated evidence/version set and policy version. Rejection creates no projection, history, alert, lock, or event mutation.

For raw five-second online/offline alternation while ODD-5 is unresolved, preserve NodeState, ConnectivityStatus, and cordon; store raw evidence; upsert exactly one current `ERR_POLICY_UNRESOLVED` diagnostic for that node; emit no flapping alert and no one-for-one transition. No hidden stabilization threshold exists.

### Invariants (I)

| ID | Deterministic invariant | AD-n | Enforcement point |
|---|---|---|---|
| I-T1 | Only the reducer selects NodeState and it evaluates the fixed precedence once per immutable fact set. | AD-4 | `NodeStatePolicy` interface and sealed signal union |
| I-T2 | Every non-`HEALTHY` state is cordoned; `HEALTHY` is uncordoned only with no active safety reason. | AD-3, AD-4 | reducer guard plus SQL `nodes_state_cordon_ck` |
| I-T3 | Every state/cordon change has one explanation with rule ID and exact evidence set. | AD-4 | unit-of-work contract and non-null audit/history fields |
| I-T4 | Raw connectivity observations never mutate public state, connectivity, cordon, or flapping alerts without approved versioned ODD-5 configuration. | AD-5 | StabilityPolicy port and reducer guard |
| I-T5 | At most one alert is open for a node/reason pair; recurrence after closure uses a new episode. | AD-5 | partial unique SQL index and AlertSink contract |
| I-T6 | `OFFLINE` recovery returns to `RECOVERING`, never directly to `HEALTHY`. | AD-4, AD-6 | transition-table guard |

### Concurrency / Idempotency

Signals share the node's ordered event stream. Simultaneous heartbeat, clock, thermal, and maintenance facts are sequenced and reduced one at a time; revision CAS prevents lost writes. Replayed signal/event IDs return the stored outcome. A tick registered after a received heartbeat is ordered after it. Alert upserts use the unique open-episode key, not check-then-insert.

### Time

The calling application obtains time from `Clock`; the reducer accepts explicit `evaluationAt`. Exact silence and tick boundaries follow AD-2. Domain code performs no wall-clock read.

### Latency budget

NFR-11 exposure ordering applies; no numeric SLA is invented.

## 3. `scheduleMaintenanceDrain(nodeId, window)`

### Operation

```text
async scheduleMaintenanceDrain(nodeId: NodeId, window: MaintenanceWindow) -> MaintenanceDrainResponse
```

`MaintenanceWindow { eventId: UUID, requestId: UUID, startsAt: UtcInstant, reason: str[1..500], expectedNodeRevision: int>=0, actor: str[1..128] }`. No end time, timeout, job action, or scheduling authority is implied.

### Layer

Inbound Port. It writes a maintenance command through the serialized processor and observes workloads through the outbound External Context Port.

### Preconditions (P)

| P | Exact requirement | Failure |
|---|---|---|
| P-M1 | `nodeId` is valid/configured and `window` fields are non-null, correctly typed, and within the exact ranges above. | `ERR_SCHEMA`/422 or `ERR_UNKNOWN_NODE`/404 |
| P-M2 | Actor is the local Carlos fixture; production RBAC is external and not claimed. | `ERR_POLICY_STATE_CONFLICT`/409 |
| P-M3 | `startsAt` is supplied by the adapter from `Clock`; it cannot precede the last accepted node event time. | `ERR_CLOCK_ORDER`/409 |
| P-M4 | `expectedNodeRevision` equals the current revision. | `ERR_REVISION_CONFLICT`/409, retryable |
| P-M5 | No different active maintenance lock exists for the node. | `ERR_MAINTENANCE_CONFLICT`/409 |
| P-M6 | Reused `requestId` has the same canonical request hash. | identical: success/200 existing result; changed: `ERR_IDEMPOTENCY_CONFLICT`/409 |

### Postconditions (Q)

Return exactly `MaintenanceDrainResponse { eventId, requestId, nodeId, outcome, lockId, nodeRevision, state, cordoned, activeWorkloadCount, activeWorkloadIds, workloadObservedAt, explanation }`. On first acceptance, atomically create the authoritative active lock, set `cordoned=true`, select `DRAINING` when workload evidence is missing/stale/pre-lock/positive (with `DRAIN_STATUS_UNKNOWN` when unknown), or `MAINTENANCE` only when an accepted snapshot has newer source revision, `observedAt >= startsAt`, `receivedAt >= startsAt`, `activeWorkloadCount=0`, and no workload IDs. Persist one audit/decision, zero-or-one history row, and emit `MaintenanceDrainScheduled` plus any state/cordon event.

Active workload IDs/count remain visible and labeled `EXTERNAL_MOCK`. The operation never emits terminate, evict, checkpoint, placement, reservation, or scheduling commands. Identical replay returns the original result with no duplicate lock, event, audit, or history. Rejection has no lock/projection/history/alert/event effect.

### Invariants (I)

| ID | Deterministic invariant | AD-n | Enforcement point |
|---|---|---|---|
| I-M1 | A node has at most one active maintenance lock and one request ID has one payload/result. | AD-1, AD-7 | partial unique SQL index plus request hash uniqueness |
| I-M2 | An accepted lock immediately cordons in the same atomic unit of work. | AD-4, AD-7 | application transaction and SQL state/cordon constraint |
| I-M3 | `MAINTENANCE` requires fresh post-lock zero count and zero IDs; all missing/stale/pre-lock/positive evidence remains `DRAINING`. | AD-7, AD-8 | MaintenancePolicy guard and workload snapshot constraints |
| I-M4 | Release/maintenance evaluation never writes `HEALTHY` directly; it invokes the full reducer. | AD-4, AD-7 | inbound port contract and reducer interface |
| I-M5 | Workload/reservation facts remain read-only external/mock context and no scheduler action is emitted. | AD-8 | outbound port surface has reads/events only, no control method |

### Concurrency / Idempotency

Concurrent equal requests serialize: one creates the lock and all identical replays receive the same stored response. Concurrent different requests for the same node result in one winner; the other receives `ERR_REVISION_CONFLICT` or `ERR_MAINTENANCE_CONFLICT`. The active-lock partial unique index is the final physical guard. No SELECT-then-UPDATE pattern is allowed. Subsequent workload snapshots use source revision and post-lock time guards before moving to `MAINTENANCE`.

### Time

`startsAt` comes from injected `Clock`. Drain has no timeout or forced-completion behavior while ODD-7 is unresolved.

### Latency budget

NFR-11 exposure ordering applies. The cordon and accepted lock must commit before a fleet version exposes the drain; no numeric latency SLA exists.

## Typed Error Catalog

| CODE | HTTP / Exit Status | Trigger | Human-readable explanation template | Retryable Y/N |
|---|---:|---|---|---|
| `ERR_SCHEMA` | 422 | Required value absent, null where forbidden, invalid type/enum/format/range | `Field {field} violates {rule}; supplied value was {value}.` | N |
| `ERR_UNKNOWN_NODE` | 404 | Validly formed node ID is not in the 32-node inventory | `Node {nodeId} is not configured in this simulation run.` | N |
| `ERR_CAPACITY_RANGE` | 422 | VRAM/storage value is outside configured bound | `{field}={observed} is outside [0,{maximum}] for {resourceId}.` | N |
| `ERR_IDEMPOTENCY_CONFLICT` | 409 | Existing event/request ID is reused with different canonical payload | `{id} was already used for a different payload.` | N |
| `ERR_ORDER_AMBIGUOUS` | 409 | Different heartbeat has equal event time and no higher sequence | `Heartbeat order cannot be resolved at {occurredAt}; provide a higher sourceSequence.` | Y |
| `ERR_LATE_EVENT` | 200 (`LATE_IGNORED`) | Older/current-or-prior-epoch telemetry arrives | `Event {eventId} is older than accepted evidence and was not applied.` | N |
| `ERR_DUPLICATE` | 200 (`DUPLICATE`) | Identical event/request replay | `{id} was already processed; the recorded result is returned.` | N |
| `ERR_BOOT_SUCCESSION` | 409 | Changed boot lacks state-loss/successor proof | `Boot session {newBoot} does not prove succession from {currentBoot}.` | N |
| `ERR_REVISION_CONFLICT` | 409 | Expected node/lock revision is stale | `Expected revision {expected}; current revision is {actual}.` | Y |
| `ERR_EVIDENCE_NOT_FOUND` | 409 | Reducer signal references absent/wrong-node/unaccepted evidence | `Evidence {evidenceId} is unavailable for node {nodeId}.` | Y |
| `ERR_CLOCK_ORDER` | 409 | Distinct tick/start time is equal to or before last accepted ordered time | `Time {supplied} must be later than {lastAccepted}.` | Y |
| `ERR_INVALID_TRANSITION` | 409 | Requested/derived edge is outside state table | `Transition {priorState}->{requestedState} is not permitted for rule {ruleId}.` | N |
| `ERR_POLICY_UNRESOLVED` | 409 | An exit/classification requires an unresolved ODD | `Policy {policyId} is unresolved; public state is held without an invented default.` | N |
| `ERR_POLICY_STATE_CONFLICT` | 409 | Mutation context or state conflicts with the local prototype contract | `Operation {operation} is not permitted in state/context {state}.` | N |
| `ERR_MAINTENANCE_CONFLICT` | 409 | A different active maintenance lock/request exists | `Node {nodeId} already has active maintenance lock {lockId}.` | N |
| `ERR_LOCK_SOURCE_MISMATCH` | 409 | Telemetry-observed lock conflicts with authoritative command lock | `Observed lock state conflicts with authoritative lock {lockId}; no automatic change was made.` | N |
| `ERR_INGRESS_UNAVAILABLE` | 503 | Adapter cannot accept/sequence input before domain acceptance | `Ingress is unavailable; event {eventId} was not accepted.` | Y |

## Invariant Binding Table

| Invariant | AD-n | Enforcement Point | Physical/Domain Enforcement | Red Test That Must Fail If Removed |
|---|---|---|---|---|
| I-H1 event ID maps to one payload/outcome | AD-1 | `telemetry_snapshots_event_id_uq`, request hash | SQL unique + ingestion guard | Replay same ID 100 times; changed hash conflicts |
| I-H2 stale telemetry cannot replace current | AD-1, AD-6 | revision/order conditional repository API | SQL conditional update + domain guard | Apply newer then older; snapshot/revision unchanged |
| I-H3 strict silence boundary | AD-2 | `HeartbeatPolicy.evaluate` | Domain guard | At exactly `3*interval` not offline; epsilon later offline |
| I-H4 thermal reason/cordon atomic | AD-3, AD-4 | reducer UoW; `nodes_state_cordon_ck` | Domain + SQL transaction/check | 88.1°C cannot commit uncordoned; 88.0°C no thermal reason |
| I-H5 monotonic reboot epoch | AD-6 | succession guard; node revision/epoch | Domain + atomic repository | `ws-gpu-05` A→B once; replay A cannot refill fields |
| I-H6 external facts stay external/nullable | AD-8 | ExternalContextPort | Interface/domain validation | Missing workload never becomes zero/maintenance |
| I-T1 sole fixed-precedence reducer | AD-4 | `NodeStatePolicy` | Domain interface | All-at-once vector produces exactly precedence-selected state |
| I-T2 non-healthy implies cordoned | AD-3, AD-4 | `nodes_state_cordon_ck` | SQL + domain | Insert/update `DEGRADED,false` fails |
| I-T3 mutation requires explanation | AD-4 | UoW + history/audit non-null fields | SQL/domain | Transition without rule/evidence fails transaction |
| I-T4 raw connectivity is evidence-only | AD-5 | StabilityPolicy port | Domain guard | 12 alternating 5-second observations cause 0 state/cordon changes |
| I-T5 one open alert per node/reason | AD-5 | `alerts_one_open_per_reason_uq` | Partial unique SQL index | Concurrent duplicate alert opens yield one row |
| I-T6 offline returns through recovery | AD-4, AD-6 | transition table guard | Domain guard | `OFFLINE` + heartbeat cannot yield `HEALTHY` |
| I-M1 one active lock/request identity | AD-1, AD-7 | `maintenance_locks_one_active_uq`, request unique | Partial/ordinary unique SQL indexes | Concurrent locks create one active record/event |
| I-M2 lock and cordon atomic | AD-4, AD-7 | DomainUnitOfWork | Transaction + SQL check | Inject persistence failure; neither lock nor cordon commits |
| I-M3 fresh post-lock zero only | AD-7, AD-8 | MaintenancePolicy | Domain guard + workload checks | Pre-lock/stale zero remains `DRAINING`; fresh zero becomes maintenance |
| I-M4 release invokes reducer | AD-4, AD-7 | Maintenance inbound port | Interface contract | Release while thermal active stays cordoned/degraded |
| I-M5 no adjacent-module control | AD-8 | outbound port inventory | Compile/static architecture check | Ports expose no terminate/place/reserve method |

Every invariant has either an exact SQL pointer or an exact domain/interface guard. No invariant relies on convention alone.
