---
title: 'Story 1.3 — Detect silence at the exact boundary (silent node → OFFLINE)'
type: 'feature'
created: '2026-10-25'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '0b3f96576a419678a7b767bfd062869c0923b998'
context: ['{project-root}/docs/epic-1-context.md', '{project-root}/docs/spec-1-1-see-the-complete-simulated-fleet.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A machine that stops reporting stays HEALTHY and eligible forever, because nothing evaluates heartbeat freshness (task annex 3.2).

**Approach:** Add an ordered clock evaluation, `evaluate_fleet_liveness(evaluation_at)`. It applies the strict AD-2 rule `evaluation_at − last_accepted_receive_at > 3 × heartbeat_interval` through the shared reducer and commits `OFFLINE` + cordon + `ERR_SILENT` alert + explanation atomically per node. A heartbeat that returns after `OFFLINE` must not jump straight back to `HEALTHY`.

## Boundaries & Constraints

**Always:** strict boundary (equal to 3 intervals is not silent); the node's configured interval only; nodes with no accepted heartbeat stay `UNKNOWN`; time only from the injected `Clock`/explicit `evaluation_at`; evaluation instants strictly increase (`ERR_CLOCK_ORDER` otherwise); reducer precedence OFFLINE > RECOVERING > DEGRADED > HEALTHY > UNKNOWN with other reasons retained; one CAS commit per transitioning node (projection, history, alert, audit); one open `ERR_SILENT` episode per node; an already-OFFLINE, still-silent node is held with no new rows; every transition explained with last receive time, interval, elapsed and missed-interval count.

**Never:** `sleep`/wall-clock reads in domain or application; new HTTP endpoints; an `OFFLINE → HEALTHY` edge (I-T6); invented recovery-exit criteria (ODD-3).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Annex silent node | `ws-gpu-12` HEALTHY, last receive 45 s ago, interval 10 s | `OFFLINE`, cordoned, connectivity `SILENT`, one open `ERR_SILENT` alert, history row, explanation `missedIntervals` 4.5 > 3 | N/A |
| Exact boundary | elapsed exactly 30 s | unchanged, no history/alert | N/A |
| Just past boundary | elapsed 30.001 s | `OFFLINE` | N/A |
| Never reported | node `UNKNOWN`, no heartbeat | unchanged `UNKNOWN` | N/A |
| Still silent | already `OFFLINE`, later evaluation | held; no new history, alert, or audit row | N/A |
| Degraded node goes silent | `DEGRADED` (driver reason) silent | `OFFLINE`; driver reason retained | N/A |
| Clock not advancing | evaluation instant ≤ previous | rejected | `ERR_CLOCK_ORDER`, nothing evaluated |
| Fleet scan | 32 nodes, 3 silent | exactly those 3 transition; result lists them | N/A |
| Return after OFFLINE | heartbeat for an `OFFLINE` node | `RECOVERING`, cordoned, `ERR_SILENT` episode closed, `RECOVERY_PENDING` held (ODD-3) | N/A |

**Decisions (human, 2026-10-25):**
- D1: Liveness runs as an in-process periodic scan started by the app lifespan, configured by `GPU_TWIN_LIVENESS_SCAN_SECONDS` (default 5, `0` disables it). No new endpoint.
- D2: A heartbeat for an `OFFLINE` node yields `RECOVERING`, still cordoned, with `RECOVERY_PENDING` retained until Story 2.2 defines exit evidence.

</frozen-after-approval>

## Code Map

- `src/gpu_lab_twin/domain/node_state.py` -- add `ReasonCode.SILENT = "ERR_SILENT"`, `ReasonCode.RECOVERY_PENDING`; reducer branches OFFLINE (silent reason) and RECOVERING; cordon invariant unchanged.
- `src/gpu_lab_twin/domain/heartbeat_policy.py` -- pure `is_silent(last_receive, evaluation_at, interval_ms)` with strict `>`.
- `src/gpu_lab_twin/domain/explanation.py` -- `explain_silence(...)`; the heartbeat explanation must cover OFFLINE → RECOVERING.
- `src/gpu_lab_twin/ports/inbound/liveness.py` (new) -- `LivenessPort.evaluate_fleet_liveness(evaluation_at) -> LivenessReport`.
- `src/gpu_lab_twin/application/liveness_service.py` (new) -- iterates the inventory under the shared write lock and tracks the last evaluation instant.
- `src/gpu_lab_twin/application/heartbeat_service.py` -- OFFLINE node + heartbeat → drop `ERR_SILENT`, add `RECOVERY_PENDING`, close the silent alert.
- `src/gpu_lab_twin/ports/outbound/node_repository.py`, `adapters/db/node_repository.py` -- `commit_transition(...)` (CAS + history + alert open/close + audit) reusing the 1.1 helpers; `close_alerts` support; current telemetry event ID for evidence.
- `src/gpu_lab_twin/api/app.py`, `bootstrap.py`, `config/settings.py` -- D1 scan task + setting.
- Reuse unchanged: `api/errors.py`, `tests/support.py` probes, migration 0001 (no schema change).

## Tasks & Acceptance

**Execution:**
- [x] `src/gpu_lab_twin/domain/*` -- silence rule, reasons, reducer branches, explanations -- AD-2/AD-4.
- [x] `src/gpu_lab_twin/ports/*`, `application/liveness_service.py`, `application/heartbeat_service.py` -- scan + OFFLINE return path -- AD-1 ordering.
- [x] `src/gpu_lab_twin/adapters/db/node_repository.py` -- atomic transition commit, alert close -- one UoW.
- [x] `src/gpu_lab_twin/api/scheduler.py`, `api/app.py`, `bootstrap.py`, `config/settings.py` -- wiring per D1 -- periodic scan in the running service.
- [x] `tests/unit/test_silence_policy.py`, `tests/unit/test_node_state_reducer.py` -- boundary vectors (property: `elapsed > 3×interval` ⇔ silent) and precedence.
- [x] `tests/integration/test_story_1_3_silent_node_detection.py` -- every matrix row + OFFLINE return path, using FakeClock only.

**Acceptance Criteria:**
- Given `ws-gpu-12` whose last heartbeat was received 45 s ago with a 10 s interval, when liveness evaluation runs, then it is `OFFLINE`, cordoned, and an `ERR_SILENT` alert (annex `NODE_SILENT_TIMEOUT`) is open.
- Given an OFFLINE node, when `GET /v1/nodes` is read, then it shows `OFFLINE`, cordoned, `SILENT` and its last-known receive time and readings (not null, not zero).
- Given any test in this story, when it runs, then no real sleep or wall-clock read occurs.

## Implementation Notes

- Implemented directly from this spec. New: `application/liveness_service.py`, `ports/inbound/liveness.py`, `api/scheduler.py` (driving adapter; injectable sleep so tests never wait). Extended: reducer (OFFLINE/RECOVERING branches driven by `ERR_SILENT`/`RECOVERY_PENDING` reasons), `heartbeat_policy.is_silent`/`missed_intervals` (exact `timedelta` arithmetic), `explain_silence`, repository `commit_transition` + alert closing, heartbeat service OFFLINE→RECOVERING path, `GPU_TWIN_LIVENESS_SCAN_SECONDS` (tests set 0).
- The liveness service shares the heartbeat write lock, so a heartbeat received before an evaluation is applied first (ARCHITECTURE §6.2) and CAS conflicts cannot occur in-process.
- `RECOVERY_PENDING` opens its own alert episode so a later retained-reason explanation can cite the evidence that activated it (pattern from Story 1.1's review).
- The Story 1.1 reducer property test encoded the old precedence; it was updated to the full OFFLINE > RECOVERING > DEGRADED > HEALTHY > UNKNOWN order (an intended reducer change, not a matrix expectation).
- Verified 94/94 on SQLite and on PostgreSQL 16.

## Spec Change Log

## Review Triage Log

Pass 1 (blind-hunter B, edge-case-hunter E, verification-gap V; subagents with no prior context):

| # | Finding | Verdict | Evidence | Route |
|---|---|---|---|---|
| B4/E2/V-o | One failed node commit aborts the whole fleet scan; `_last_evaluation_at` not advanced | medium | Confirmed: an exception inside the per-node loop escaped `evaluate_fleet_liveness` | patch: per-node isolation, `failed_node_ids` in the report, test with a monkeypatched failure |
| V1/B9b | Lifespan never starts the scan in any test (setting forced to 0) | medium (pre-verified gap) | Only `run_periodically` unit-tested | patch: wiring test (task, period, cancellation) + default-value test |
| B6 | Silence explanation omits reasons still active under OFFLINE and their evidence | medium | `explain_silence` ignored `reason_evidence` | patch: `retainedReasonEvidence`, evidence IDs and summary tail; test |
| E6 | Silence judged against the stored interval, not the configured inventory | low | `seed_inventory` never refreshes stored nodes; direct correction | patch: use `spec.heartbeat_interval_ms`; test |
| B2/E5 | Explicit future `evaluation_at` accepted, then blocks later scans | low | Only internal callers, but a direct guard | patch: `ERR_CLOCK_ORDER` when `evaluation_at > clock.now()`; test |
| B3/E1 | Naive `evaluation_at` raises `TypeError` | low | Direct guard | patch: `ERR_SCHEMA`; test |
| B10/E8 | Scan period accepts 0.001/inf; domain rejections logged as crashes | medium | `ge=0` only; `logger.exception` for every error | patch: 0 or ≥ 0.1 s, finite; DomainError logged as warning; test |
| B10b | Detection latency vs "exact boundary" undocumented | low | Direct doc fix | patch: README section |
| B7 | `elapsedSeconds` float may round at sub-ms boundaries | low | Direct addition | patch: exact `elapsedMicroseconds` |
| B8/E9 | Annex name `NODE_SILENT_TIMEOUT` never recorded | low | Direct addition | patch: `annexEventName` in the audit body; asserted |
| V2 | `driverHealth` threshold rule unasserted | low (pre-verified gap) | Only `recoveryPolicy` key checked | patch: exact thresholds asserted for DEGRADED and RECOVERING |
| B11 | No tests for RECOVERING→silent→return, OFFLINE→RECOVERING history | medium | Absent | patch: two tests |
| B12 | Fleet-scan test does not prove the other nodes are untouched | low | Absent assertion | patch: 27 untouched nodes asserted |
| V3 | Storage failure (IntegrityError) inside `commit_transition` unexercised | medium (unverified) | Mapping and atomicity not tested; isolation now tested | defer |
| B1/E4 | Clock-order guard is in memory and lost on restart | low | A backwards evaluation can only see less elapsed time, so it cannot mark a node OFFLINE early; persisting it adds state (process-local baseline, NFR-12) | reject |
| E3 | Wall-clock step back pauses scans until the clock catches up | low | Contract P-T3 requires rejecting non-increasing instants; scans resume automatically; now logged as a warning | reject |
| B9 | Shutdown can race an in-flight scan thread | low | Container engines are disposed only for production builds; an in-flight transaction finishes or rolls back atomically | reject |
| B5 | Wrong error code for a failed scan write | false | CAS conflicts raise `ERR_REVISION_CONFLICT` as documented; IntegrityError maps to the generic not-accepted code | reject |
| B13 | Spec/sprint status mismatch, Code Map wording, empty logs, concurrent alert opens | false/low | Sprint moves to review at step-05; logs are written now; the partial unique index guards opens; fixing the Code Map wording would edit the spec | reject |

## Verification

**Commands:**
- `.venv/Scripts/python -m pytest -q` -- expected: all pass, 0 skipped
- `.venv/Scripts/ruff check src tests migrations && .venv/Scripts/ruff format --check src tests migrations` -- expected: clean
