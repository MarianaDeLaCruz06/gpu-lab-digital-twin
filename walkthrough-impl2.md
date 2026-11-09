# Impl-2 Walkthrough — Module 3: GPU Lab Digital Twin

Team: Mariana De La Cruz / Julian Motta. Method: BMad 6.12 with TEA (Murat), `bmad-build` (Amelia), Full Ceremony.
Scope: Impl-1 stories 3.1–3.3 plus the three complex Annex stories 3.4–3.6.

This report links to the underlying evidence instead of repeating it. Every number below comes from a captured log in `evidence/impl2/` or a run recorded in this file. Nothing is estimated.

## 1. Quick verification (single commands)

| What | Command | Result (2026-11-08, Windows 11, clean checkout of `main` + this branch) |
|---|---|---|
| Unit + integration + acceptance | `uv run --extra dev pytest` | **437 passed**, 0 failed, 0 skipped |
| Branch coverage | `uv run --extra dev pytest --cov=gpu_lab_twin --cov-branch` | Total 90%; core domain 96–100% (see §6) |
| Playwright E2E | `npm ci && npx playwright install chromium && npx playwright test` | **1 passed** (6 steps), 0 retries |
| k6 NFR | `K6_PROFILE=adapted k6 run tests/nfr/telemetry-storm.js` (or `scripts/run-story-3-5-nfr.ps1 -Profile adapted`) | Adapted formal gate **PASS** in CI: p95 8.2 ms, p99 10.6 ms, 0 failed, RSS 84 MiB (see §4.2). The Annex 2,000/s `full` profile stays as RED evidence |

CI (`.github/workflows/ci.yml`) runs three jobs on every push and PR: lint + pytest on SQLite and PostgreSQL 17 + migration round-trip; Playwright E2E with `--trace on`, which uploads `trace.zip` and the HTML report as the `playwright-traces` artifact; and `nfr-k6`, which runs the k6 smoke profile and the **adapted formal Story 3.5 gate** while sampling the service RSS (it fails above 200 MB). CI run 42561772122 passed all three jobs. The Annex 2,000 events/s profile is not run in CI; it is kept as RED evidence (§4.2, I2-DL-15).

## 2. Architectural hardening and concurrency defense

The Impl-1 Ports & Adapters layout was extended. It was not restructured.

- **Single ordered write path (AD-1).** Every mutation goes through one process-wide write lock plus a repository revision compare-and-swap. Heartbeats, connectivity observations and maintenance commands share this sequencer, so ordering and idempotency are global and deterministic.
- **Idempotency everywhere.** Heartbeats (`eventId`), connectivity observations (audit-ledger unique `event_id`) and maintenance drains (request ID + payload hash) replay their original result. Reusing an ID with a different payload fails atomically with typed `ERR_IDEMPOTENCY_CONFLICT` (HTTP 409). Nothing is partially written.
- **Alert deduplication in the database.** The `alerts_one_open_per_reason_uq` partial unique index plus atomic upsert keeps at most one open alert per node and reason, even under concurrent writers. Story 3.4 reuses this index instead of adding a second alert system.
- **Bounded memory on the hot path.** Story 3.5 adds a fixed-size, peak-preserving 100 ms window per node (10 Hz) as a *secondary projection* after the canonical atomic commit. Heartbeat semantics are never dropped or batched lossily.
- **Maintenance as an atomic lock (AD-7).** Story 3.6 acquires the maintenance lock, cordons the node, and records audit and history in one repository transaction. Completion is accepted only with a fresh workload snapshot taken after the lock.
- **Concurrency hammers.** `tests/integration/test_concurrency_hammer.py` uses a barrier to release 16 to 96 threads at once against the real app and database. 16 simultaneous drains allocate exactly one maintenance lock (zero double allocation). 16 replays of one heartbeat apply it once. A whole-fleet burst keeps `ingest_offset` unique and gapless, and the newest sequence wins on every node. With the AD-1 lock removed, the same tests fail with two locks, 5xx responses and offset collisions: `evidence/impl2/concurrency/hammer-mutation-no-lock.txt`.
- **Structured errors, not crashes.** Every domain rejection maps to a typed error body. Under the overload in §4.2 the custom unhandled-5xx metric stayed at 0%: the service refused connections but never returned an unhandled 500.
- **Deterministic time.** All time-dependent logic uses the injected `Clock` port; tests use `FakeClock.advance/set`. The project-owned code under `src/`, `tests/` and `scripts/` contains zero `time.sleep(`, `asyncio.sleep(` or `waitForTimeout(` calls (grep re-checked 2026-11-08).

## 3. Testing flows applied

| Flow | Where | Evidence |
|---|---|---|
| A — ATDD-First | Story 3.4 | Authentic RED before production code: `evidence/impl2/atdd/story-3.4-red.txt`; GREEN: `story-3.4-green.txt`; commits `ce1c634` (RED) → `7e21c79` (impl) → `ac74093` (green) |
| B — Test-Along | Stories 3.4 (policy unit tests), 3.5, 3.6 | Domain code and tests are in the same commits, e.g. `e28c43d`, `1f494bf` |
| C — Test-After | Impl-1 + Impl-2 domain hardening | Coverage gaps closed in `b44e412`; then `tests/unit/test_domain_decision_tables.py` (280 table-driven cases: the full AD-4 reducer table, AD-2/AD-3 edges, capacity ranges, AD-6, AD-7, 10 Hz bucketing). These are characterization tests that passed on their first run, so they are not claimed as ATDD (I2-DL-17) |
| D — Quality Gate / NFR | Story 3.5 (+ concurrency for all) | k6 `tests/nfr/telemetry-storm.js`, adapted gate in CI job `nfr-k6`, runner `scripts/run-story-3-5-nfr.ps1`, `evidence/impl2/nfr/story-3.5-adapted-ci.md`; concurrency hammers in `tests/integration/test_concurrency_hammer.py` |
| E — Playwright E2E + POM | Story 3.6 | `tests/e2e/pages/FleetMapPage.ts`, `tests/e2e/story-3.6-maintenance-drain.spec.ts`, `evidence/impl2/playwright/` |

### Test pyramid (actual counts)

| Layer | Tests | Share |
|---|---:|---:|
| Unit (`tests/unit`) | 346 | 78.8% |
| Integration (`tests/integration`, real SQLite/PostgreSQL) | 85 | 19.4% |
| Acceptance (`tests/acceptance`, ATDD) | 6 | 1.4% |
| E2E browser (`tests/e2e`) | 1 journey (6 steps) | 0.2% |
| NFR (k6) | 1 script, 4 profiles (smoke, adapted, full, ramp) | — |

The 70/20/10 target is met at the bottom of the pyramid: unit tests are above 70% and integration is at 20%. The unit layer runs in about half a second with no network, database or clock. Browser E2E is deliberately one complete journey with six verified steps, which avoids the ice-cream cone. Before this PR the suite was 43% unit and 53% integration. The added decision tables (Flow C) rebalance it without removing any integration test that proves AD-1 atomicity against a real database.

### The four testing traps

| Trap | Status |
|---|---|
| Ice-cream cone | Avoided: 1 E2E journey vs 431 unit/integration tests |
| Flaky sleeper | Avoided: zero sleeps/`waitForTimeout`; Playwright uses only web-first `expect(...).toHaveText/toHaveCount` |
| Mocking mirage | Avoided: integration tests use real repositories; Playwright drives the real FastAPI backend (`playwright.config.ts` `webServer`), no route mocking. AI proposal to mock the UI backend was rejected (I2-DL-07) |
| Blindly green | Avoided: ATDD RED proves the tests could fail; each assertion checks state, eligibility, alert counts or typed error codes |

## 4. The three complex stories

### 4.1 Story 3.4 — Anti-flapping hysteresis (Flow A, ATDD-First)

**Technical challenge.** The Annex asks for a new `FLAPPING_CORDONED` state after more than 3 transitions in 60 s. The team's binding Plan-2/Solu-2 contract (AD-5, ODD-5) leaves the flapping threshold *unresolved* and forbids inventing one: raw connectivity observations must be evidence-only, the public state/connectivity/cordon tuple must stay stable, no flapping alert may fire, and at most one `ERR_POLICY_UNRESOLVED` diagnostic may exist. The human decision was contract over Annex (I2-DL-01/02). The Annex scenario (`ws-gpu-14`, 5-second pulses) is kept as the test input.

**Code.** `domain/connectivity_policy.py` (pure policy), `ports/inbound/connectivity.py`, `application/connectivity_service.py`, and repository operations that record each pulse once in the audit ledger and upsert one diagnostic.

**Red phase (before any production code, HEAD `3abc6f2`):**

```
FFFF                                                                     [100%]
FAILED ...::test_ac1_five_second_pulses_preserve_stable_public_tuple_and_eligibility[12]
FAILED ...::test_ac2_exact_threshold_and_just_beyond_do_not_invent_odd5_policy
FAILED ...::test_ac3_unique_pulses_create_one_diagnostic_zero_flapping_alerts_and_one_audit_each
FAILED ...::test_ac4_duplicate_is_idempotent_and_conflicting_reuse_is_rejected_atomically
4 failed in 1.19s
E       AssertionError: AC requires a connectivity observation inbound port
```

The failure is the genuinely missing inbound port, not a fixture or import error (`evidence/impl2/atdd/story-3.4-red.txt`).

**Green.** All acceptance tests pass, plus `tests/unit/test_connectivity_policy.py`. The full suite was 138 passed at that commit and is 437 passed now. Verdict: **PASS**.

### 4.2 Story 3.5 — Telemetry storm and downsampling (Flow D, NFR)

**Technical challenge.** Absorb 2,000 heartbeats/s from 32 nodes for 60 s, downsample to 10 Hz while preserving the true peak GPU temperature within 1%, keep RSS under 200 MB, and never return an unhandled 5xx. The binding contract requires each heartbeat to be durably and atomically committed, in global order, before it is acknowledged (AD-1, FR-2/FR-3).

**Code.** `domain/telemetry_downsampling.py` (bounded per-node ring window that keeps the maximum), wired after commit in `application/heartbeat_service.py` and `bootstrap.py`. SQLite file databases get WAL, `busy_timeout` and `synchronous=NORMAL` (`adapters/db/engine.py`).

**Functional verification (PASS).** `tests/unit/test_telemetry_downsampling.py` and `tests/integration/test_story_3_5_telemetry_storm.py` prove 10 Hz output, bounded memory and exact peak retention (0% error at stored precision, so within the 1% budget).

**k6 load results.**

| Profile | Backend | Target | Achieved | p95 | p99 | HTTP failed | Unhandled 5xx | Max RSS | Verdict |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| Smoke | SQLite | 5 req/s × 5 s | 25/25 req | 72.49 ms | 90.01 ms | 0.00% | 0.00% | 103.18 MiB | PASS |
| **Adapted (formal gate, CI)** | SQLite | 32 req/s × 60 s | 1,921 req at 32.0/s, 0 dropped | **8.2 ms** | **10.6 ms** | 0.00% | 0.00% | **84.0 MiB** | **PASS** |
| FULL (formal) | SQLite | 2,000 req/s × 60 s | ~66 req/s, 112,551 dropped | 50.14 s | 58.04 s | 55.45% | 0.00% | 316.03 MiB | **RED** |
| Ramp (diagnostic) | SQLite | 100–1,000 req/s × 10 s | saturates at ~71–78 req/s | — | — | failures from 500 req/s | 0.00% | — | diagnostic |
| Ramp (diagnostic) | PostgreSQL 17.11 | 100–2,000 req/s × 10 s | peak 20.57 canonical req/s | 10.87 s at 100 | 10.99 s at 100 | 97.63% at 2,000 | 0 | 454 MiB at 2,000 | diagnostic |

Sources: `evidence/impl2/nfr/story-3.5-adapted-ci.md` (CI run 42561772122), `evidence/impl2/nfr/story-3.5-smoke-stdout.txt`, `story-3.5-full-red-summary.md`, `story-3.5-ramp-analysis.md`, `story-3.5-postgres-ramp-summary.md`.

**Diagnosis.** The bottleneck is the contract-mandated synchronous path: one multi-statement transaction per heartbeat under the global write lock (`docs/story-3-5-nfr-bottleneck-analysis.md`). Proposals to relax thresholds, drop heartbeats or overwrite the RED logs were rejected (I2-DL-09/10/11).

**Follow-up branch (not merged, not modified).** `feature/story-3.5-nfr-remediation` adds durable batching with ack-after-commit and raises PostgreSQL throughput to a peak of 37.33 canonical req/s (1.8×). It is still far from 2,000 req/s and remains Mariana's open experiment.

**Formal adaptation (I2-DL-15).** A 2026-11-08 profile showed about 11 ms per heartbeat, almost all of it in the AD-1 atomic commit. The team kept AD-1, choosing integrity over raw throughput, and used the Annex rule that stories may be adapted. The formal gate is now 32 events/s × 60 s, which is 10× the fleet's configured heartbeat load, with p95 < 250 ms, p99 < 500 ms, zero failed requests, zero dropped iterations and RSS < 200 MB. The target came from a measured local probe with about 2× headroom (see the Renegotiation section of `docs/spec-3-5-telemetry-storm.md`). The 2,000 events/s numbers above are left exactly as measured.

**Verdict.** Functional behavior: **PASS**. Adapted formal NFR gate: **PASS** in CI (p95 8.2 ms, p99 10.6 ms, 0 failed, RSS 84 MiB). The Annex 2,000 events/s figure is **not met** and is documented as the capacity limit of the AD-1 design.

### 4.3 Story 3.6 — Maintenance drain and interactive fleet map (Flow E, Playwright)

**Technical challenge.** Drive the AD-7 maintenance lock from a real browser: 32-node grid → select the dual-GPU server → drain (immediately `DRAINING` + cordoned) → idempotent replay → typed conflict on a changed replay → simulated workload completion → `MAINTENANCE`. The Annex alias `server-gpu-01` is shown only as a UI label; the canonical domain ID `central-gpu-server` stays authoritative.

**Code.** `domain/maintenance.py`, `application/maintenance_service.py`, `api/routes/maintenance.py` (canonical `/v1/...` routes), `api/routes/ui.py` (`/technician/fleet-grid`), maintenance migration and models. Page Object `tests/e2e/pages/FleetMapPage.ts` holds every selector; the spec reads as the user story.

**Badges and refusal of new work (added 2026-11-08).** The state badge uses the Annex colours: green `HEALTHY` → amber `DRAINING` → blue `MAINTENANCE`. `FleetMapPage.expectState` checks the text, the `data-tone` and the computed background colour on both the detail panel and the server's grid card. A final step proves that new work for the drained server is refused: the fleet reports it cordoned, and a fresh request returns a typed **409 `ERR_MAINTENANCE_CONFLICT`**. Module 3 owns no job dispatcher (scheduling belongs to Modules 4/9/10), so this is the module-local equivalent of the Annex "dispatch returns 409 Node Cordoned".

**Run log (2026-11-08, after the badge and 409 steps were added):**

```
Running 1 test using 1 worker
  ✓  1 [chromium] › tests\e2e\story-3.6-maintenance-drain.spec.ts:6:1 › Carlos drains server-gpu-01 without duplicate locks and sees maintenance (2.0s)
  1 passed (10.4s)
```

CI job `e2e-playwright` in run 42561772122 passed the same spec and uploaded a fresh `trace.zip`.

**Trace confirmation.** `playwright.config.ts` sets `trace: 'on-first-retry'`. A forced-trace run produced `evidence/impl2/playwright/story-3.6-trace.zip` (41 entries: DOM snapshots, network, console). Open it with `npx playwright show-trace evidence/impl2/playwright/story-3.6-trace.zip`. CI uploads a fresh trace on every run. Log: `evidence/impl2/playwright/playwright-run-trace-on.txt`.

Verdict: **PASS**.

## 5. Sprint status

`docs/sprint-status.yaml` → `assignment_story_status`: all six stories (3.1–3.6) are `done`. Story 3.5 moved from `review` to `done` once the adapted formal gate passed in CI (I2-DL-15).

## 6. Coverage (branch, 2026-11-08 run, 437 tests)

| Module | Branch cover |
|---|---:|
| `domain/heartbeat_policy.py`, `node_state.py`, `connectivity_policy.py`, `telemetry_downsampling.py`, `maintenance.py`, `heartbeat.py`, `node.py`, `errors.py` | 100% |
| `domain/fleet.py` | 98% |
| `domain/explanation.py` | 96% |
| Package total | 90% |

`application/heartbeat_batch_writer.py` shows 0% on `main` because it is only wired on the unmerged remediation branch.

## 7. Governance

- AI decisions: `docs/ai-decision-log-impl2.md` has 17 entries, 16 of them human MODIFY or REJECT decisions (`docs/ai-decision-log.md` links to it), including rejected AI testing shortcuts: hard waits and UI mocking (I2-DL-07), relaxed NFR thresholds (I2-DL-09), skipping failing tests (I2-DL-08), accepting concurrency tests that were never seen failing (I2-DL-16), and mirror-oracle unit tests (I2-DL-17).
- Traceability and quality gate: `test/traceability-matrix.md` (Impl-2 gate section).
- Intake and Annex conflicts: `docs/impl2-intake-audit.md`; NFR assessment: `_bmad-output/test-artifacts/nfr-assessment.md`.
