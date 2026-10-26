# Impl-1 Implementation Walkthrough — Module 3: GPU Lab Digital Twin

**Team:** Mariana De La Cruz · Julian Motta  
**Scope:** foundation scaffold and the three core stories of task annex Module 3, built with the BMad Method Full Ceremony (`bmad-sprint-planning` → `bmad-build` per story with the Amelia dev persona and three independent reviewers).  
**Result:** 130 automated tests pass on SQLite (0 failed, 0 skipped). Ruff lint and formatting checks are clean. The pre-remediation 126-test suite also passed on PostgreSQL 16; the compose stack was verified end to end on PostgreSQL 17.

## 1. Annex stories → team contract

The annex's three Module 3 stories conflict with the team's own Solu-2 OpenAPI contract and architectural invariants (AD-n). The task's non-negotiable rule is "endpoints must match *your* OpenAPI contract", and the annex allows "other similar stories", so we implemented the epics that cover each annex story under the team contract (decision I1-DL-02):

| Annex story | Epic story (`planning/epics.md`) | Annex wording | Team contract (implemented) |
|---|---|---|---|
| 3.1 Heartbeat ingestion & fleet state | **1.1** See the complete simulated fleet | `POST /api/v1/telemetry/heartbeat` → 202 | `POST /v1/nodes/{nodeId}/heartbeats` → 200 `APPLIED`, plus `GET /v1/nodes` |
| 3.2 Silent node → OFFLINE | **1.3** Detect silence at the exact boundary | `evaluate_fleet_liveness`, alert `NODE_SILENT_TIMEOUT` | Same routine, AD-2 strict boundary; alert reason `ERR_SILENT` (annex name recorded in the audit row) |
| 3.3 Thermal cordon | **2.1** Cordon an overheating workstation | `>= 88 °C` → `CORDONED_THERMAL` | AD-3 strict `> 88 °C` → `DEGRADED` + `cordoned=true`, reason `ERR_THERMAL_88` |

Every annex Given/When/Then scenario (65 °C/12288 MB, 45 s silence with a 10 s interval, 91 °C) passes as an automated test and in the live smoke run (§5).

## 2. Architecture

Reducer-centric **Ports & Adapters**. Dependencies point inward. One pure reducer selects every state (AD-4), and every write is a single compare-and-swap transaction (AD-1).

```text
src/gpu_lab_twin/
├── domain/          node_state.py (states, reasons, fixed-precedence reducer) · fleet.py (32-node inventory rules)
│                    heartbeat.py · heartbeat_policy.py (validation, boot succession, thermal, silence) · explanation.py · errors.py
├── ports/inbound/   HeartbeatPort · LivenessPort · FleetQueryPort          (use cases)
├── ports/outbound/  NodeRepository (atomic commits) · Clock                (driven)
├── application/     heartbeat_service.py · liveness_service.py · fleet_query.py
├── adapters/db/     SQLAlchemy 2.0 models, repository (CAS, alert upserts on partial unique index)
├── adapters/sim/    fleet fixture loader · FakeClock          adapters/clock/  SystemClock (only wall-clock read)
├── api/             FastAPI routes, DTOs, ErrorBody mapping, liveness scheduler (driving adapter)
├── config/          environment settings (validated at startup)
└── bootstrap.py     composition root
fixtures/fleet.json  31 × 1×24 GB workstations + 1 × 2×48 GB server (32 nodes, 33 GPUs, 840 GB)
migrations/          Alembic 0001 — mirrors docs/contracts/schema.sql for the Impl-1 tables
```

- **Precedence:** `OFFLINE > RECOVERING > DEGRADED > HEALTHY > UNKNOWN` (maintenance arrives in Epic 3). Every non-`HEALTHY` state is cordoned, enforced in the reducer and by the DB check `nodes_state_cordon_ck`.
- **Guarded boundaries:** `tests/unit/test_architecture.py` fails if `domain/`, `ports/` or `application/` import FastAPI, Pydantic, SQLAlchemy, adapters, `random`, GPU tooling, or read the wall clock.
- **Errors:** every non-happy path returns the contract `ErrorBody` (`code`, `message`, `retryable`, `details`). Covered codes: 404 `ERR_UNKNOWN_NODE`; 422 `ERR_SCHEMA`/`ERR_CAPACITY_RANGE`; 409 `ERR_IDEMPOTENCY_CONFLICT`/`ERR_ORDER_AMBIGUOUS`/`ERR_BOOT_SUCCESSION`/`ERR_REVISION_CONFLICT`/`ERR_CLOCK_ORDER`/`ERR_POLICY_UNRESOLVED`; 503 `ERR_INGRESS_UNAVAILABLE`.
- **Contract changes (OpenAPI 1.0.0 → 1.1.0, `docs/contracts/openapi.yaml`):** added `/health`, `/ready` and `GET /v1/nodes` (ARCHITECTURE §9.4, which Solu-2's OpenAPI omitted). The three mutation operations are unchanged. Each addition is logged in `docs/ai-decision-log.md`.

## 3. Foundation scaffold (commit `a0fda5a`)

- One-command setup: `pip install -e ".[dev]"` then `pytest` (in-memory SQLite, FakeClock, no Docker or network). `docker compose up` runs PostgreSQL + API (`alembic upgrade head`, fleet seeding, `/ready`).
- Startup fails closed if `fixtures/fleet.json` is not exactly the canonical inventory. `/ready` returns 503 if the stored fleet diverges.
- Seeded nodes start `UNKNOWN` and cordoned (PRD FR-1). The Solu-2 test fixture that seeded `HEALTHY` was rejected (I1-DL-04).
- Settings are validated through `GPU_TWIN_*` environment variables (`.env.example`).

## 4. Stories

### Story 1.1 — Heartbeat ingestion & complete fleet view (annex 3.1) · commit `0b3f965`

- **Goal:** ingest simulated heartbeats and keep the current operational state of all 32 machines.
- **Endpoints:**
  - `POST /v1/nodes/{nodeId}/heartbeats` returns `APPLIED` (or `DUPLICATE` for an identical replay) with node revision, state, cordon, connectivity and a structured explanation.
  - `GET /v1/nodes` returns 32 summaries in inventory order. Missing telemetry is `null`, never 0, and the endpoint fails closed with 503 if the store diverges.
- **Database:** an accepted heartbeat writes, in one transaction:
  - a revision-CAS update of `nodes`;
  - a `telemetry_snapshots` row (unique `event_id`, SHA-256 `payload_hash`, global `ingest_offset`, one `is_current` per node) plus its `telemetry_gpu_samples`, carrying the actual `APPLIED`, `LATE_IGNORED`, or `BOOT_CHANGE_DETECTED` disposition;
  - `node_state_history` only when state or cordon changes;
  - an `alerts` upsert for each reason re-observed by this heartbeat;
  - an `audit_events` row holding the recorded response for idempotent replay.
- **Rules:**
  - Validation is all-or-nothing: exact GPU membership, capacity ranges, finite values, and receive time not later than the server clock.
  - Driver `UNHEALTHY`/`UNKNOWN` sets `DEGRADED` + cordon.
  - A degradation reason is retained until an approved clear rule exists.
  - Older/non-increasing telemetry is persisted as `LATE_IGNORED` without replacing current telemetry. Proven boot succession produces `BOOT_CHANGE_DETECTED`, increments the evidence epoch, and enters `RECOVERING`; unproven succession returns `ERR_BOOT_SUCCESSION`.
- **Tests:** `tests/integration/test_story_1_1_heartbeat_ingestion.py`, `test_fleet_view.py`, `test_revision_cas.py`, `tests/unit/test_heartbeat_policy.py`, and `test_node_state_reducer.py` cover all advertised dispositions, persistence, rejection non-effects, and reducer behavior.

### Story 1.3 — Silent node detection & OFFLINE transition (annex 3.2) · commit `16c4d80`

- **Goal:** mark nodes that miss more than 3 heartbeat intervals as `OFFLINE` and exclude them from new work.
- **Trigger:** `LivenessService.evaluate_fleet_liveness()`. An in-process scan runs every `GPU_TWIN_LIVENESS_SCAN_SECONDS` (default 5 s), and tests call it with FakeClock. There is no new endpoint (decision D1).
- **Rules:**
  - A node is silent only if `elapsed > 3 × configured interval`, so exactly 30 s is not silent.
  - Nodes that never reported stay `UNKNOWN`.
  - Evaluation instants must strictly advance.
  - One failing node never stops the fleet scan.
  - A heartbeat after `OFFLINE` gives `RECOVERING`, still cordoned, until ODD-3 defines recovery evidence. There is never an `OFFLINE → HEALTHY` edge (decision D2).
- **Database:** for each transitioning node, `commit_transition` does a revision-CAS `nodes` update (`OFFLINE`, `SILENT`, `ERR_SILENT`), adds a history row, upserts the `ERR_SILENT` alert episode and writes an audit row (`NodeSilenceDetected`, `annexEventName: NODE_SILENT_TIMEOUT`). When the node returns, the silence episode closes and a `RECOVERY_PENDING` episode opens.
- **Tests:** `tests/integration/test_story_1_3_silent_node_detection.py` (16 functions, 18 cases), `test_liveness_scan_wiring.py` (3 functions, 5 cases), `tests/unit/test_silence_policy.py` (4 functions, 7 cases incl. a Hypothesis boundary property), `test_scheduler.py` (2).

### Story 2.1 — Automated thermal anomaly cordoning (annex 3.3) · commit `74cb068`

- **Goal:** automatically cordon any node whose GPU temperature exceeds 88 °C.
- **Endpoints:** the existing heartbeat route (thermal is a reason inside ingestion). Unavailability is visible as `cordoned=true` in the response and in `GET /v1/nodes` (decision D1).
- **Rules:**
  - The thermal reason fires when any GPU reads strictly above 88 °C; one hot GPU cordons the whole node.
  - Measurements are quantized to the stored 3-decimal precision, so decisions match the recorded evidence.
  - The explanation cites the hottest GPU, its value, the threshold `{"operator": ">", "value": 88}` and `ERR_THERMAL_88`.
  - The reason is retained after cooling while ODD-4 (thermal release policy) is unresolved, and the explanation cites the activating reading.
- **Database:** no schema change. The reason, cordon, `DEGRADED` state, alert episode and explanation are part of the same heartbeat transaction.
- **Tests:** `tests/integration/test_story_2_1_thermal_cordon.py` (12), `tests/unit/test_thermal_policy.py` (4 functions, 8 cases incl. a Hypothesis property).

Every story has at least 2 tests that map directly to its Gherkin scenario. Those tests are marked with the annex scenario as a comment.

## 5. Evidence

### Automated test runner (`pytest -v --cov`)

```text
tests/integration/test_story_1_1_heartbeat_ingestion.py::test_valid_heartbeat_updates_node_and_receive_time PASSED
tests/integration/test_story_1_1_heartbeat_ingestion.py::test_unknown_node_is_404_with_zero_effects PASSED
tests/integration/test_story_1_1_heartbeat_ingestion.py::test_exact_replay_returns_recorded_result_without_new_effects PASSED
tests/integration/test_story_1_3_silent_node_detection.py::test_silent_node_goes_offline_cordoned_with_alert_and_explanation PASSED
tests/integration/test_story_1_3_silent_node_detection.py::test_exactly_three_intervals_is_not_silent PASSED
tests/integration/test_story_1_3_silent_node_detection.py::test_heartbeat_after_offline_enters_recovering_not_healthy PASSED
tests/integration/test_story_2_1_thermal_cordon.py::test_thermal_emergency_cordons_immediately_and_is_visible_as_unavailable PASSED
tests/integration/test_story_2_1_thermal_cordon.py::test_exactly_88_does_not_activate_the_rule PASSED
tests/unit/test_architecture.py::test_inner_layers_do_not_import_frameworks_or_outer_layers[domain] PASSED
...
TOTAL                                                 1282     35    164     19    96%
============================ 130 passed in 14.73s =============================
```

Before B01/B02 remediation, the then-current 126 tests passed against PostgreSQL 16 (`GPU_TWIN_TEST_DATABASE_URL=…/gpu_lab_twin_test pytest`). The current 130-test suite passed on SQLite; CI (`.github/workflows/ci.yml`) runs the suite on PostgreSQL 17. The suite refuses any database whose name does not end in `_test`.

### Live smoke run against `docker compose up` (PostgreSQL 17, real clock)

```text
GET /ready -> {"status":"ready","nodes":32,"gpuDevices":33}
3.1 heartbeat ws-gpu-04 65C -> 200 APPLIED HEALTHY cordoned False
3.1 unknown node -> 404 ERR_UNKNOWN_NODE
3.3 heartbeat ws-gpu-19 91C -> 200 DEGRADED cordoned True ['ERR_THERMAL_88'] {'temperatureC': {'operator': '>', 'value': 88}}
3.2 heartbeat ws-gpu-12 then silence -> 200 HEALTHY
    waiting 40 s (interval 10 s, threshold > 30 s, scan every 5 s)...
3.2 after silence: {'nodeId': 'ws-gpu-12', 'state': 'OFFLINE', 'cordoned': True, 'connectivityStatus': 'SILENT', 'activeReasonCodes': ['ERR_SILENT']}
3.3 fleet entry:   {'nodeId': 'ws-gpu-19', 'state': 'OFFLINE', 'cordoned': True, 'connectivityStatus': 'SILENT', 'activeReasonCodes': ['ERR_SILENT', 'ERR_THERMAL_88']}
fleet nodeCount: 32
```

(After 40 s with no further heartbeats every reporting node is silent; the hot node keeps its thermal reason under `OFFLINE`, as the precedence requires.)

### BMad traceability

- `docs/sprint-status.yaml` holds Impl-1's commitment and validates with `sprint_plan.py validate`. Git history demonstrates planning, implementation, review/remediation, and final human review. The intermediate `in-progress` status was not persisted contemporaneously, so no historical timestamp is reconstructed. On 2026-10-26 Mariana approved Story 1-1 with a minor documentation concern and approved Stories 1-3 and 2-1; their current status is `done`.
- Each story spec records its approved decisions, Implementation Notes and the full Review Triage Log (one row per reviewer finding with verdict and evidence):
  - `docs/spec-1-1-see-the-complete-simulated-fleet.md`
  - `docs/spec-1-3-detect-silence-at-the-exact-boundary.md`
  - `docs/spec-2-1-cordon-an-overheating-workstation.md`
- Review totals across the 3 stories: 59 triage entries (each groups one or more raw reviewer findings with the same root cause). 37 were patched, 3 deferred (`docs/deferred-work.md`) and 19 rejected with evidence. Per story: 1.1 had 24 entries (16/1/7), 1.3 had 19 (13/1/5) and 2.1 had 16 (8/1/7).
- `docs/ai-decision-log.md`: 18 AI interaction entries plus one genuine human-governance record, including corrected defects such as a falsy-zero offset bug, a clock read outside the write lock, a fleet scan that aborted on one node, and a float-vs-stored-precision mismatch.

### Human review outcome (2026-10-26)

- Reviewer: Mariana De La Cruz (A00399618).
- Story 1-1 / annex 3.1: **APPROVED WITH MINOR DOCUMENTATION CONCERN**; the stale checklist and walkthrough statements were corrected.
- Story 1-3 / annex 3.2: **APPROVED**.
- Story 2-1 / annex 3.3: **APPROVED**.
- Technical blockers remaining: **0**. B01 added canonical `maintenance_locks` schema/model coverage; B02 completed canonical heartbeat disposition behavior.

## 6. Known limits (documented, not hidden)

- **Single process (NFR-12 baseline).** Writes are serialized by an in-process lock. Run one worker. A multi-process sequencer is deferred.
- **Out of sprint:** Story 1.2 (late/out-of-order heartbeats are not yet `LATE_IGNORED`), 2.2 (reboot recovery; reboots fail closed), 2.3 (flapping), Epic 3 (maintenance), Epic 4. The UI dashboard is not part of Impl-1.
- **Unresolved open design decisions are held fail-safe, never defaulted:** ODD-3 (recovery exit), ODD-4 (thermal release), ODD-5/6 (flapping).
- **Solu-2 suite:** the RED contract suite in `test/` is kept as Solu-2 evidence and is outside the default `pytest` run. Its in-scope vectors (HB-FRESH, HB-INVALID, HB-SILENCE, HB-THERMAL-001/002, SC-ISOLATION) are re-implemented in `tests/`.
