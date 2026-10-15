# Module 3 Event Contracts

All event fields use camelCase. Every envelope contains non-null `eventId` (UUID), `occurredAt` (RFC 3339 UTC instant), and `schemaVersion` (`"1.0"`). Node identifiers follow the contract regex. Payloads reject unknown fields at ingress. Events carry facts and explanations only; none controls reservations, jobs, GPUs, Kubernetes, inference, catalog, or enterprise observability.

## Ingested events

### `HeartbeatReceived`

```json
{
  "eventId": "7ed33825-f0ab-4ad4-b45e-3fce7178fcaa",
  "occurredAt": "2026-10-15T14:05:03Z",
  "receivedAt": "2026-10-15T14:05:03Z",
  "schemaVersion": "1.0",
  "nodeId": "ws-gpu-14",
  "bootSessionId": "boot-a",
  "previousBootSessionId": null,
  "stateLoss": false,
  "sourceSequence": 42,
  "gpuSamples": [{"gpuDeviceId":"ws-gpu-14-gpu-0","temperatureC":88.1,"vramOccupiedGb":4.0}],
  "driverHealth": "HEALTHY",
  "storageFreeGb": 320.0,
  "externalContext": null
}
```

Disposition is `APPLIED`, `DUPLICATE`, `LATE_IGNORED`, or `BOOT_CHANGE_DETECTED`. Identical `eventId` replay has no new effects; changed-payload reuse conflicts.

### `ConnectivityObserved`

Fields: envelope + `nodeId`, `status: ONLINE|OFFLINE`, `receivedAt`. Raw observations are evidence-only until a versioned ODD-5 policy is approved. The mandatory 5-second alternating sequence does not change public state/cordon/connectivity and creates no flapping alert under the unresolved baseline.

### `ClockEvaluated`

Fields: envelope + `evaluationAt`. A distinct tick must be strictly later than the prior accepted tick. It evaluates strict silence through the ordered node stream using injected time.

### `WorkloadSnapshotReceived`

Fields: envelope + `snapshotId`, `nodeId`, `source: EXTERNAL_MOCK`, `sourceRevision >= 0`, `receivedAt`, `activeWorkloadCount >= 0`, `activeWorkloadIds`. Count must equal list length. Only a newer, post-lock zero snapshot may complete drain.

### `MaintenanceDrainRequested`

Fields: envelope + `requestId`, `nodeId`, `startsAt`, `reason`, `expectedNodeRevision`, `actor`. This creates/returns an authoritative lock and never requests workload action.

## Emitted events

Every emitted event includes the common envelope and `nodeId`, `nodeRevision`, and `explanation` matching `ExplanationDTO`.

### `HeartbeatApplied`

Additional fields: `sourceEventId`, `outcome`, `state`, `cordoned`, `connectivityStatus`, `telemetryId`. It is emitted only on a first applied heartbeat, not duplicate/late disposition.

### `NodeStateTransitioned`

Additional fields: `sourceEventId`, `priorState`, `state`, `priorCordoned`, `cordoned`, `activeReasonCodes`. Exactly one is emitted for a committed public state change.

### `NodeCordoned`

Additional fields: `sourceEventId`, `state`, `cordoned: true`, `activeReasonCodes`. Thermal explanation includes rule `ERR_THERMAL_88`, observed GPU/value, and threshold `{temperatureC:{operator:">",value:88}}`.

### `AlertEpisodeOpenedOrUpdated`

Additional fields: `sourceEventId`, `alertId`, `reasonCode`, `openedAt`, `lastObservedAt`, `updateCount`. Only one open episode exists per `(nodeId, reasonCode)`. Raw unresolved flapping observations do not emit this event.

### `PolicyDiagnosticUpserted`

Additional fields: `sourceEventId`, `code: ERR_POLICY_UNRESOLVED`, `policyId`, `evidenceIds`. Repeated unclassified connectivity observations update one current diagnostic rather than flooding alerts.

### `RebootDetected`

Additional fields: `sourceEventId`, `priorBootSessionId`, `bootSessionId`, `evidenceEpoch`, `state: RECOVERING`, `cordoned: true`. `ws-gpu-05` is the mandatory example; prior-epoch replay emits nothing.

### `MaintenanceDrainScheduled`

Additional fields: `requestId`, `lockId`, `state: DRAINING|MAINTENANCE`, `cordoned: true`, `activeWorkloadCount` (nullable), `activeWorkloadIds`, `workloadObservedAt` (nullable). Missing evidence remains visibly unknown, never zero.

### `MaintenanceDrainCompleted`

Additional fields: `sourceEventId`, `lockId`, `snapshotId`, `state: MAINTENANCE`, `cordoned: true`, `activeWorkloadCount: 0`, `activeWorkloadIds: []`. Requires fresh post-lock evidence.

### `AuditRecorded`

Additional fields: `sourceEventId`, `eventType`, `ruleIds`, `evidenceIds`, `outcome`, and structured body. It contains no secret or personal data. Duplicate replay returns the existing audit reference and does not emit another event.
