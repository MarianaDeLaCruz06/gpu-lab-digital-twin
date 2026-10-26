---
title: 'Story 1.1 — See the complete simulated fleet (heartbeat ingestion + fleet view)'
type: 'feature'
created: '2026-10-25'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '69b3ce212256198af033b7df5fdfbd8d3b304707'
context: ['{project-root}/docs/epic-1-context.md', '{project-root}/docs/contracts/openapi.yaml']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The twin seeds 32 nodes in `UNKNOWN`, but nothing can ingest telemetry or show the fleet, so Carlos cannot see live state (task annex 3.1).

**Approach:** Implement `ingestHeartbeat` behind `POST /v1/nodes/{nodeId}/heartbeats` exactly as the OpenAPI contract defines (validate → reduce → one atomic CAS commit → `APPLIED` + explanation), introduce the shared fixed-precedence reducer, and expose a read-only fleet projection of all 32 nodes.

## Boundaries & Constraints

**Always:** all-or-nothing validation with zero mutation on rejection; GPU samples equal exactly the node's configured device IDs; VRAM/storage within capacity; finite non-negative numbers; reducer alone selects state (precedence DRAINING>MAINTENANCE>OFFLINE>RECOVERING>DEGRADED>HEALTHY>UNKNOWN); non-HEALTHY ⇒ cordoned; node write is `UPDATE … WHERE revision=:expected`; projection, snapshot, GPU samples, history (only on state/cordon change), alert upserts and audit commit in one transaction; every response carries an `ExplanationDTO`; driver `UNHEALTHY`/`UNKNOWN` activate `ERR_DRIVER_UNHEALTHY`/`ERR_DRIVER_HEALTH_UNKNOWN` (DEGRADED, cordoned); degradation reasons are retained until an approved clear rule exists; time comes from the injected `Clock`.

**Never:** endpoints or fields outside the OpenAPI contract; trusting client-supplied state/cordon; zero-filling missing telemetry; wall-clock reads in domain/application; ordering/late-event logic (Story 1.2), silence (1.3), thermal (2.1), reboot recovery (2.2).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| First heartbeat | `ws-gpu-04` UNKNOWN; 65 °C, 12 GB VRAM, driver HEALTHY | 200 `APPLIED`, HEALTHY, cordoned=false, ONLINE, revision 1, `last_accepted_receive_at`=clock now | N/A |
| Unknown node | `ws-gpu-99` | 404 `ERR_UNKNOWN_NODE` | no row changes |
| Malformed node ID / body | `WS_BAD`, missing field, extra field, bad enum | 422 `ERR_SCHEMA` | no row changes |
| Foreign GPU ID | `ws-gpu-09` reports `ws-gpu-10-gpu-0` | 422 `ERR_SCHEMA` | neither node changes |
| Over capacity | VRAM 25 GB on 24 GB GPU; storage > 500 GB | 422 `ERR_CAPACITY_RANGE` | no row changes |
| Driver degraded | driver UNKNOWN | 200 `APPLIED`, DEGRADED, cordoned, alert opened | N/A |
| Exact replay | same eventId + payload | 200 `DUPLICATE`, recorded response, no new rows | N/A |
| ID reuse | same eventId, different payload | 409 `ERR_IDEMPOTENCY_CONFLICT` | no row changes |
| Fleet view | after seeding | 32 summaries, unknown telemetry = `null`, never 0 | N/A |
| Boot change, no proof | `bootSessionId` differs, no `stateLoss`/`previousBootSessionId` | 409 `ERR_BOOT_SUCCESSION` | no row changes |
| Boot change, proven | `stateLoss=true` or matching `previousBootSessionId` | 409 `ERR_POLICY_UNRESOLVED` (`ODD-3`) | no row changes |
| Future receive time | `payload.receivedAt` later than Clock now | 422 `ERR_SCHEMA` | no row changes |

**Decisions (human, 2026-10-25):**
- D1: `GET /v1/nodes` is added to the contract (OpenAPI 1.1.0) from ARCHITECTURE §9.4; Solu-2's OpenAPI omitted it.
- D2: Boot changes fail closed as in the matrix until Story 2.2.
- D3: The server `Clock` instant is authoritative for `received_at`/`acceptedAt`; `payload.receivedAt` must not be later than it. Contract P-H2's literal equality is not enforced.

</frozen-after-approval>

## Code Map

- `src/gpu_lab_twin/domain/node_state.py` -- add `NodeFacts`, `Decision`, pure `evaluate()` reducer; keep existing enums.
- `src/gpu_lab_twin/domain/heartbeat.py` (new) -- `HeartbeatPayload`/`GpuSample` value objects, canonical SHA-256 payload hash.
- `src/gpu_lab_twin/domain/heartbeat_policy.py` (new) -- membership/capacity/boot-succession validation, driver reasons.
- `src/gpu_lab_twin/domain/explanation.py` (new) -- `Explanation` value object + contract-shaped document.
- `src/gpu_lab_twin/domain/node.py` (new) -- `NodeSnapshot` read model of the aggregate.
- `src/gpu_lab_twin/ports/inbound/heartbeat.py`, `ports/inbound/fleet.py` (new) -- use-case protocols.
- `src/gpu_lab_twin/ports/outbound/node_repository.py` -- extend with `get_node`, `find_heartbeat`, `commit_heartbeat`, `list_fleet`.
- `src/gpu_lab_twin/application/heartbeat_service.py`, `application/fleet_query.py` (new) -- orchestration; process-local lock serializes writers and assigns `ingest_offset`.
- `src/gpu_lab_twin/adapters/db/node_repository.py` -- CAS update, inserts, alert upsert via the partial unique index, IntegrityError → typed errors.
- `src/gpu_lab_twin/api/schemas.py`, `api/routes/telemetry.py`, `api/routes/nodes.py`, `api/app.py`, `bootstrap.py` -- DTOs ported from `planning/detailed-design/schemas/dto.py`; reuse `api/errors.py` mapping unchanged.
- `docs/contracts/openapi.yaml` -- add `GET /v1/nodes` + `FleetResponse`/`NodeSummary`.
- Do not change: migration 0001, `fixtures/fleet.json`, the `test/` Solu-2 suite.

## Tasks & Acceptance

**Execution:**
- [x] `src/gpu_lab_twin/domain/*` -- value objects, validation, reducer, explanation -- pure core per AD-4.
- [x] `src/gpu_lab_twin/ports/*` -- inbound/outbound protocols -- dependency inversion.
- [x] `src/gpu_lab_twin/application/*` -- services -- AD-1 single ordered writer.
- [x] `src/gpu_lab_twin/adapters/db/node_repository.py` -- atomic commit + fleet read -- one UoW.
- [x] `src/gpu_lab_twin/api/*`, `bootstrap.py`, `docs/contracts/openapi.yaml` -- routes/DTOs/wiring -- contract compliance.
- [x] `tests/unit/test_node_state_reducer.py`, `tests/unit/test_heartbeat_policy.py` -- reducer precedence and validation edge cases.
- [x] `tests/integration/test_story_1_1_heartbeat_ingestion.py`, `tests/integration/test_fleet_view.py` -- every matrix row through HTTP with zero-mutation probes.

**Acceptance Criteria:**
- Given node "ws-gpu-04" registered, when a heartbeat with 65 °C and 12288 MB (12 GB) VRAM arrives, then its record and `last_accepted_receive_at` update to the current Clock instant and the response is 200 `APPLIED` (contract status; the annex says 202).
- Given any rejected heartbeat, when it is processed, then node, telemetry, history, alert and audit row counts and revisions are unchanged.
- Given a state change, when committed, then exactly one `node_state_history` row with non-empty rule and evidence IDs exists for that revision.

## Implementation Notes

- Implemented directly from this spec (no subagent dispatch). New: `domain/{heartbeat,heartbeat_policy,explanation,node}.py`, `application/{heartbeat_service,fleet_query}.py`, `ports/inbound/{heartbeat,fleet}.py`, `api/routes/{telemetry,nodes}.py`; extended: reducer in `domain/node_state.py`, `NodeRepository` port + SQL adapter, `api/schemas.py`, `bootstrap.py`, OpenAPI 1.1.0 (`GET /v1/nodes`).
- Surprise (caught by `test_state_change_writes_exactly_one_explained_history_row`): `max(ingest_offset) or -1` treated offset 0 as "no rows" and reissued 0 to the second heartbeat (unique violation → 503). Replaced with SQL `COALESCE(MAX(ingest_offset) + 1, 0)`.
- Unmapped `IntegrityError`s are now logged before becoming `ERR_INGRESS_UNAVAILABLE`; a reused `sourceSequence` maps to `ERR_ORDER_AMBIGUOUS` (409) instead of a 503.
- Added `tests/integration/test_revision_cas.py`: no matrix row exercised the CAS conflict branch (AD-1).
- `GPU_TWIN_TEST_DATABASE_URL` runs the whole suite on PostgreSQL; verified 65/65 on SQLite and on PostgreSQL 16 (ON CONFLICT over the partial index, `RETURNING`, `text[]`).
- Hypothesis profile `deterministic` (no deadline, derandomized): one load-dependent deadline flake was observed during the PostgreSQL run.
- Pydantic serializes UTC as `Z`; tests compare parsed instants, not strings.

## Spec Change Log

## Review Triage Log

Pass 1 (blind-hunter B, edge-case-hunter E, verification-gap V; subagents with no prior context):

| # | Finding | Verdict | Evidence | Route |
|---|---|---|---|---|
| E1 | Clock read before the write lock, so a later commit can carry an older `received_at` | medium | Confirmed: `at = self._clock.now()` preceded `with self._write_lock` | patch: read time and validate under the lock |
| E2 | Clock regression lets receive time move backwards (or breaks `alerts_observed_order_ck` → 503) | medium | No guard compared `at` with `last_accepted_receive_at` | patch: `ERR_CLOCK_ORDER` 409 + test |
| E12 | "AD-1 single ordered writer" claim not met | medium | Same root cause as E1 for in-process ordering; cross-process part is B3 | grouped with E1 |
| B3/E8 | Offset/serialization single-process only, undocumented | medium | `threading.Lock` + `MAX+1` offset; nothing documented the limit | patch: documented in README + Dockerfile (single worker); DB sequencer deferred |
| B1/E11 | Fleet read is 4 SELECTs without one snapshot on PostgreSQL READ COMMITTED | medium | Plain session, default isolation | patch: REPEATABLE READ on PostgreSQL |
| B5/E6 | Canonical hash depends on UTC offset notation and GPU sample order | medium | `isoformat()` kept the client offset; samples hashed in arrival order | patch: UTC normalization + sorted samples + test |
| B6/E5 | Retained reasons refresh alert `update_count`/`last_observed_at` | medium | `alert_reasons` used all active reasons | patch: only re-observed reasons upsert; test now asserts `update_count == 1` |
| B7 | Retained-reason explanation cites only the current heartbeat as evidence | medium | `evidence_ids=(payload.event_id,)` | patch: activating evidence from open alert episode added to `evidenceIds` and `retainedReasonEvidence` |
| B8b/B9/E9/E10/E13 | `GET /v1/nodes` returns partial fleet (200) or `KeyError` on DB/inventory divergence; no error response in contract | medium | `self._order[...]` lookup; no completeness check; only 200 declared | patch: fail closed with `ERR_INGRESS_UNAVAILABLE` 503, declared in route + OpenAPI, test |
| B4/E7 | IntegrityError mapped by bare substring `"event_id"` also matches `source_event_id` | low | `str(exc.orig)` substring; direct correction | patch: match constraint names / `table.column` markers |
| B11/V1 | `UNHEALTHY` driver path untested end to end | medium (pre-verified gap) | Only `reasons_from` unit-tested | patch: reducer + HTTP tests parametrized over both drivers |
| V2 | `storageCapacityGb` never value-checked | low (pre-verified gap) | No test read the field | patch: assertions 500 / 4000 |
| B11 | NaN at HTTP boundary and cross-node `eventId` reuse untested | low | No such tests | patch: two tests |
| B12 | Determinism property is tautological; precedence unverified | low | Called a pure function 50× | patch: replaced by precedence property |
| B13 | Test fixture `drop_all` on any `GPU_TWIN_TEST_DATABASE_URL` | medium | No safeguard | patch: refuse databases not ending in `_test` (verified) |
| B14d | `RecordedHeartbeat.node_id` unused | low | Direct correction | patch: reported as `recordedNodeId` in the 409 |
| V3/B4b | `event_id` IntegrityError branch and concurrent-replay race unexercised | medium (unverified in single process) | Unreachable while the in-process lock serializes writers | defer |
| B2 | Fleet projection has no version | low | Spec intent asks for a complete fleet read; no Impl-1 consumer compares versions; adding it is new public surface | reject |
| B8a | Contract hardcodes 32 nodes | false | FR-1/NFR-1 fix the inventory at exactly 32 nodes for a run | reject |
| B8c | Response DTOs do not repeat contract constraints | low | Values come from the validated inventory; contract tests validate every response; fix adds guards | reject |
| B10 | `ERR_ORDER_AMBIGUOUS` mapping outside the matrix | low | Without it a reused `sourceSequence` is a 503; recorded in Implementation Notes; fix would edit the spec | reject |
| B14a-c | Port docstring/`at`, spec vs sprint status, empty logs | false | Docstring states `at` comes from the Clock; sprint moves to review in step-05; logs are written in step-04 | reject |
| E3 | `occurredAt` later than receive time accepted | low | Contract does not forbid source clock skew; ordering semantics belong to Story 1.2; fix adds a guard | reject |
| E4 | Unknown stored reason code raises `ValueError` | low | Codes are written only by this reducer; unreachable without manual DB edits; fix adds a guard | reject |

## Verification

**Commands:**
- `.venv/Scripts/python -m pytest -q` -- expected: all pass, 0 skipped
- `.venv/Scripts/ruff check src tests migrations && .venv/Scripts/ruff format --check src tests migrations` -- expected: clean
