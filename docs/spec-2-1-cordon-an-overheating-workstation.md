---
title: 'Story 2.1 — Cordon an overheating workstation (thermal cordon)'
type: 'feature'
created: '2026-10-25'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '16c4d801b0e45a0e67c534e72dbc861a03eacfe2'
context: ['{project-root}/docs/epic-2-context.md', '{project-root}/docs/spec-1-1-see-the-complete-simulated-fleet.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A heartbeat reporting a GPU above 88 °C is applied as HEALTHY and eligible, so overheating hardware can keep receiving work (task annex 3.3).

**Approach:** Add the AD-3 thermal reason `ERR_THERMAL_88` (any GPU temperature strictly above 88 °C) to heartbeat evaluation. The existing reducer and the atomic heartbeat commit then select `DEGRADED` (or a higher-precedence state), force the cordon, open one thermal alert episode, and explain the GPU, value, threshold, and rule in the same transaction.

## Boundaries & Constraints

**Always:** strict `> 88` (88.0 does not trigger); any single GPU triggers the whole node; reason, cordon, state, alert and explanation commit atomically before the node is visible; explanation `thresholds.temperatureC == {"operator": ">", "value": 88}` and `observedValues` carry the hottest GPU ID and value; precedence OFFLINE > RECOVERING > DEGRADED with thermal retained underneath; the thermal reason is retained (ODD-4 unresolved) and cited as `ERR_POLICY_UNRESOLVED` until a clear rule exists; a cooler heartbeat does not refresh the thermal alert.

**Never:** `>=` comparison; a thermal clear/hysteresis value; per-GPU eligibility; new endpoints or schema changes; fan or power control.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Annex thermal emergency | `ws-gpu-19` HEALTHY; heartbeat 91 °C | 200 `APPLIED`, `DEGRADED`, cordoned, `ERR_THERMAL_88` alert open, fleet view shows cordoned | N/A |
| Just above threshold | `ws-gpu-14` 88.1 °C | `DEGRADED`, cordoned, explanation 88.1 vs `>` 88 | N/A |
| Exactly threshold | `ws-gpu-14` 88.0 °C | `HEALTHY`, not cordoned, no thermal rule or alert | N/A |
| One hot server GPU | server GPUs 91 °C and 40 °C | whole node `DEGRADED`/cordoned; explanation names `central-gpu-server-gpu-0` | N/A |
| First heartbeat hot | `UNKNOWN` node, 95 °C | `UNKNOWN → DEGRADED`, cordoned | N/A |
| Cooled afterwards | thermal active; next heartbeat 70 °C | still `DEGRADED`/cordoned; `ERR_POLICY_UNRESOLVED` cited with the activating evidence; alert not refreshed | N/A |
| Thermal + driver | 91 °C and driver `UNKNOWN` | `DEGRADED`; both reasons and both thresholds cited | N/A |
| Hot return after OFFLINE | `OFFLINE` node; heartbeat 91 °C | `RECOVERING` (precedence), thermal reason active and alerted | N/A |
| Hot node goes silent | thermal active; silence > 3 intervals | `OFFLINE`; thermal retained and cited | N/A |

**Decisions (human, 2026-10-25):**
- D1: `cordoned=true` (heartbeat response and `GET /v1/nodes`) is the "refuse placement/allocation" signal. Placement and reservation stay with Modules 4/9/10, so no eligibility endpoint is added.

</frozen-after-approval>

## Code Map

- `src/gpu_lab_twin/domain/node_state.py` -- add `ReasonCode.THERMAL = "ERR_THERMAL_88"`, include it in `DEGRADATION_REASONS`; no reducer change needed.
- `src/gpu_lab_twin/domain/heartbeat_policy.py` -- `THERMAL_THRESHOLD_C = 88`; `reasons_from` adds thermal when `max_temperature_c > 88`.
- `src/gpu_lab_twin/domain/heartbeat.py` -- hottest-sample helper for the explanation.
- `src/gpu_lab_twin/domain/explanation.py` -- thermal threshold/observed GPU in `explain_heartbeat_decision`; the driver threshold only for driver reasons.
- Reuse unchanged: heartbeat service, repository commit, alert upsert/closing, retained-reason evidence, liveness scan (thermal retained under OFFLINE automatically).
- `test/` Solu-2 HB-THERMAL-001/002 expectations (88.1 → DEGRADED + `ERR_THERMAL_88`; 88.0 → no thermal rule) are the reference vectors.

## Tasks & Acceptance

**Execution:**
- [x] `src/gpu_lab_twin/domain/node_state.py`, `heartbeat_policy.py`, `heartbeat.py`, `explanation.py` -- thermal reason, strict rule, explanation -- AD-3/AD-4.
- [x] `tests/unit/test_heartbeat_policy.py`, `tests/unit/test_node_state_reducer.py` -- boundary property (`max > 88` ⇔ thermal) and precedence collisions.
- [x] `tests/integration/test_story_2_1_thermal_cordon.py` -- every matrix row through HTTP and the liveness scan.

**Acceptance Criteria:**
- Given `ws-gpu-19` is `ONLINE`/HEALTHY, when a heartbeat with GPU temperature 91 °C is received, then it is immediately `DEGRADED` with `cordoned=true` (annex `CORDONED_THERMAL`) and is shown as unavailable in the fleet view.
- Given any accepted heartbeat with a GPU above 88 °C, when the response or any later read is observed, then `cordoned` is never false while the thermal reason is active.

## Implementation Notes

- Implemented directly from this spec. `ReasonCode.THERMAL = "ERR_THERMAL_88"` joins `DEGRADATION_REASONS` (driver codes split into `DRIVER_REASONS` so each threshold is cited only for its own reason). `THERMAL_THRESHOLD_C = 88` with strict `>` in `reasons_from`. `HeartbeatPayload.hottest_sample` breaks ties by lowest device ID so explanations do not depend on sample order.
- No reducer, service, repository or schema change was needed: Stories 1.1/1.3 already provide atomic commit, alert episodes, retained-reason evidence, and precedence under OFFLINE/RECOVERING. This confirms the reducer-centric design (AD-4).
- Verified 123/123 on SQLite and on PostgreSQL 16.
- Correction to the task list: boundary and precedence unit tests are in `tests/unit/test_thermal_policy.py` (not `test_heartbeat_policy.py`/`test_node_state_reducer.py`).
- Review patches: measurements quantized to the persisted 3-decimal precision at the API boundary; retained-thermal explanations cite the activating reading; per-reason clear policies named. Final: 126/126 on SQLite and PostgreSQL 16.

## Spec Change Log

## Review Triage Log

Pass 1 (blind-hunter B, edge-case-hunter E, verification-gap V; subagents with no prior context):

| # | Finding | Verdict | Evidence | Route |
|---|---|---|---|---|
| B1 | Thermal decided on the raw float, but `temperature_c` is stored as NUMERIC(7,3): 88.0001 cordons while 88.000 is recorded | medium | Confirmed in `models.py`; replay from stored evidence would disagree | patch: quantize measurements to 3 decimals at the API boundary (`MEASUREMENT_DECIMALS`); tests for 88.0004 → HEALTHY and 88.0006 → DEGRADED with stored values |
| B2/E1/V-o | Retained-thermal explanation pairs the cool current reading with the `> 88` threshold; activating GPU/value missing | medium | Only the evidence ID pointed back | patch: `activatingTemperatureC`/`activatingGpuDeviceId` from the open episode's recorded observation; asserted |
| B3 | Unresolved clear policy not named (ODD-4) | low | Generic `"clearPolicy": "unresolved"` | patch: per-reason `clearPolicy` with `policyId` (ODD-4 thermal, ODD-3 recovery, UNASSIGNED driver); asserted |
| V1/B9 | Hottest-GPU naming only tested when GPU 0 is hot | medium (pre-verified gap) | Both assertions used gpu-0 | patch: `(40, 91)` → `central-gpu-server-gpu-1` test |
| B8 | Repeated hot readings untested (one episode, `update_count` 2) | low | Absent | patch: test |
| B7 | RECOVERING test did not read back reasons | low | Absent assertions | patch: `ruleIds` and fleet `activeReasonCodes` asserted, silence cleared |
| B12 | "Never eligible while hot" not read back via `GET /v1/nodes` after cooling | low | Absent | patch: fleet assertion after the cool heartbeat |
| B10 | Tie-break comment says "lowest" but sorts lexicographically | low | Direct comment fix (nodes have at most 2 GPUs) | patch: comment corrected |
| E2 | A >88 °C heartbeat that also carries reboot evidence is rejected (409) and the node stays eligible | medium | Contract: rejected input mutates nothing; Story 1.1 decision D2 fails reboots closed until Story 2.2 | defer (Story 2.2 accepts proven reboots, after which thermal applies) |
| B4/V-o/E4 | Spec task list names the wrong unit-test files | low | Tests live in `tests/unit/test_thermal_policy.py`; fix edits the spec | reject (recorded in Implementation Notes) |
| B5 | Spec/sprint status mismatch; no PostgreSQL command in Verification | false | Sprint moves to review at step-05; the PostgreSQL run is documented in README and Implementation Notes | reject |
| B6 | MAINTENANCE/DRAINING precedence untested | false | Those states do not exist until Epic 3 | reject |
| B11 | `hottestGpuDeviceId` on every explanation, undocumented | low | `observedValues` is an open object in the contract | reject |
| E3 | Silence explanation for a hot node omits thermal threshold/clear policy | low | It already cites the retained reason and its activating evidence; the decision being explained is silence | reject |
| V-o | Reducer property derives expectations from `DEGRADATION_REASONS` | low | Integration tests fail if THERMAL leaves the set | reject |
| V-o | Solu-2 HB-THERMAL vectors in `test/` are not collected | false | Intentional: the Solu-2 RED suite is outside `testpaths` (README); the same vectors are covered by the new tests | reject |

## Verification

**Commands:**
- `.venv/Scripts/python -m pytest -q` -- expected: all pass, 0 skipped
- `.venv/Scripts/ruff check src tests migrations && .venv/Scripts/ruff format --check src tests migrations` -- expected: clean
