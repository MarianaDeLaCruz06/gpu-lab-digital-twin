# Epic 1 Context: Live Fleet Awareness

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Carlos (Hardware Lab Technician) and Alex (Graduate Researcher) can open a complete simulated 32-machine fleet, ingest current heartbeat telemetry end to end, and distinguish fresh from silent nodes without physical hardware. This epic is the walking skeleton through fixture, domain, persistence port, and API: every later protection (thermal, reboot, flapping, maintenance) builds on the heartbeat ingestion path and node projection established here.

## Stories

- Story 1.1: See the complete simulated fleet
- Story 1.2: Keep telemetry ordered and exactly-once
- Story 1.3: Detect silence at the exact boundary

## Requirements & Constraints

- The fleet is fixed for a run: 31 workstations (one 24 GB GPU, 500 GB storage) and one server (two 48 GB GPUs, 4 TB storage) — 32 nodes, 33 GPUs, 840 GB VRAM. Every fleet read contains each node exactly once. Nodes start `UNKNOWN` and cordoned until an accepted heartbeat establishes state.
- Heartbeat validation is all-or-nothing: the node must exist; GPU samples must match exactly the node's configured device IDs; temperatures finite and non-negative; occupied VRAM within each GPU's capacity; free storage within node capacity; driver health is `HEALTHY | UNHEALTHY | UNKNOWN`. A rejected heartbeat changes nothing, on any node, and returns a typed error (`ERR_UNKNOWN_NODE` 404, `ERR_SCHEMA` / `ERR_CAPACITY_RANGE` 422).
- An accepted heartbeat returns `APPLIED` with node revision, state, cordon, connectivity, accepted time, and a structured explanation (rule IDs, observed values, thresholds, evidence IDs, policy version, prior/result state, summary). Identical event-ID replay returns the recorded result (`DUPLICATE`) with no new effects; the same ID with a different payload is `ERR_IDEMPOTENCY_CONFLICT` 409.
- Older or equal-ambiguous telemetry must never overwrite newer state (`LATE_IGNORED`, `ERR_ORDER_AMBIGUOUS`).
- Silence is true only when a first accepted heartbeat exists and `evaluation_time − last_accepted_receive_time > 3 × configured interval`; equality is not silent. A silent node becomes `OFFLINE`, cordoned, with an alert episode and an explanation citing last receive time, interval, and elapsed interval count. A node with no heartbeat stays `UNKNOWN`. Stale/duplicate heartbeats cannot reset the silence clock.
- No wall-clock reads or sleeps in domain logic; all time comes from an injected clock. Zero physical GPU or adjacent-module calls.
- Missing or stale values are never presented as zero or current.

## Technical Decisions

- Stack: Python, FastAPI, Pydantic v2 DTOs (camelCase on the wire), SQLAlchemy 2.0 + Alembic, PostgreSQL target with SQLite for tests, pytest.
- Reducer-centric hexagonal architecture: handlers only produce facts/reasons; one pure reducer selects state by fixed precedence `DRAINING > MAINTENANCE > OFFLINE > RECOVERING > DEGRADED > HEALTHY > UNKNOWN`. Every non-`HEALTHY` state forces `cordoned=true` (also a DB check constraint).
- Single ordered writer per node: one monotonic ingest offset per accepted input; node mutations commit by compare-and-swap on `nodes.revision` (`UPDATE … WHERE revision = :expected`), never select-then-update. Projection, telemetry snapshot, GPU samples, history (only on state/cordon change), alert, and audit rows commit in one transaction; every state/cordon change carries an explanation.
- Persistence tables: `nodes`, `gpu_devices`, `telemetry_snapshots` (unique `event_id`, canonical SHA-256 `payload_hash`, unique `ingest_offset`, one `is_current` per node), `telemetry_gpu_samples`, `node_state_history`, `alerts` (one open per node+reason), `audit_events`.
- Contract operation: `POST /v1/nodes/{nodeId}/heartbeats` (200 / 404 / 409 / 422 / 503), `IngestHeartbeatRequest`/`IngestHeartbeatResponse`, `ErrorBody {code, message, retryable, details}`. Silence evaluation is a separate ordered clock signal into the reducer, not part of heartbeat ingestion.
- `ONLINE` is a connectivity status, not a node state.
- Heartbeat interval (ODD-1) is per-node configuration (10 s in the canonical fixture).

## UX & Interaction Patterns

- Fleet Dashboard reads one complete, versioned fleet projection with all 32 node summaries; it never derives state itself. Silent nodes show `OFFLINE`, cordoned, and last-known timestamp.
- Loading, Empty, Error, Success, and Denied UI states bind to response DTOs and the `ErrorBody` contract; a rejected ingestion shows Error/Denied, never a partial fleet.

## Cross-Story Dependencies

- 1.1 establishes the node projection, telemetry persistence, and `last_accepted_receive_at` that 1.3 evaluates.
- 1.2 hardens 1.1's ingestion with ordering and idempotency guarantees; 1.3 is listed after 1.2.
- Epic 2 (thermal cordon, reboot, flapping) reuses the heartbeat path and reducer from this epic.
