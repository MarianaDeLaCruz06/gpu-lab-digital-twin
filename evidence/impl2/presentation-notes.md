# Impl-2 Presentation Evidence

Module 3 — GPU Lab Digital Twin. Team: Mariana De La Cruz / Julian Motta. Branch: `feature/impl2`. Updated 2026-11-07 (continuation run; no automatic commits created).

## A. Process / problems / learnings

- **Story 3.4 (anti-flapping):** Annex conflict with canonical Plan-2/Solu-2 (AD-5/ODD-5 unresolved). Human decision: reject invented `FLAPPING_CORDONED`/numeric threshold; implement evidence-only containment with one unresolved diagnostic. Flow A/ATDD-First used with authentic RED evidence at missing connectivity seam, then GREEN/refactor.
- **Story 3.5 (telemetry storm):** Requirement implemented as a bounded 100 ms (10 Hz) peak-preserving *secondary projection* after canonical atomic heartbeat commit, preserving FR-2/FR-3 semantics. Learning: do not treat lossy ingestion as acceptable; keep heartbeat effects canonical and memory bounded.
- **Story 3.5 NFR evidence discipline:** LOCAL_SMOKE (real k6 smoke against local service) is useful but not proof of the formal FULL profile (2,000 events/s, 32 nodes, 60s). Continuation could not run FULL because `k6`/`.tools/k6.exe` was unavailable — reported as CONCERNS, not fabricated PASS.
- **Story 3.6 (Fleet drain):** Real-backend Playwright E2E verified 32-node Fleet Grid, drain start (DRAINING/unavailable), idempotent reuse, typed conflict (`ERR_IDEMPOTENCY_CONFLICT`), simulated workload completion to MAINTENANCE. No mocks bypassing application logic; no hard waits.
- **Continuation baseline issue:** `pytest --cov` / normal pytest previously hit 5 errors in migration/fleet-inventory tests. Diagnosed as **WINDOWS / environment file-locking/permission issue** (`tmp_path` base `C:\Users\maria\AppData\Local\Temp\pytest-of-maria` permission denied), not application/test-logic defect. Fixed by approved writable `--basetemp` and legitimate SQLAlchemy engine disposal in migration tests.

## B. Module working + tests at all levels

### Regression (continuation, 2026-11-07)
- Command: `uv run pytest -q --basetemp=C:\Users\maria\AppData\Local\Temp\opencode\pytest-basetmp`
- **Collected: 147 | Passed: 147 | Failed: 0 | Errors: 0 | Skipped: 0**
- Quality: `uv run ruff check .` PASS; `uv run ruff format --check .` PASS (131 files). Project-owned `src/tests/scripts` contain no `time.sleep(`, `sleep(` as hard test waits, or `waitForTimeout(` matches.

### Branch coverage (continuation)
- Command: `uv run pytest --cov=gpu_lab_twin --cov-branch --cov-report=xml:evidence/impl2/coverage/coverage.xml --cov-report=html:evidence/impl2/coverage/html`
- **TOTAL 95%** (1773 statements, 65 missed, 240 branches, 37 partial). Core domain modules >=90% where relevant: `telemetry_downsampling` 100%, `heartbeat_policy` 100%, `connectivity_policy` 100%, `maintenance` 96%, `explanation` 96%, `node_state` 94%, `heartbeat`/`node`/`errors` 100%; `fleet.py` 89% (minor uncovered domain branches). **Core-domain branch coverage target >=90%: PASS (evidence-backed).** Evidence: `evidence/impl2/coverage/`.

### Story 3.4
- ATDD RED: `evidence/impl2/atdd/story-3.4-red.txt`. GREEN: `evidence/impl2/atdd/story-3.4-green.txt` and acceptance/unit tests pass. Verdict: PASS.

### Story 3.5 (remediated, truthfully reported)
- Downsampler/integration tests PASS (10 Hz, bounded projection, peak/max retention => 0% at stored precision, <=1%). Full regression 147 passed/0 failed/0 errors/0 skipped; branch coverage 95% (>=90% core domain); ruff clean.
- **LOCAL_SMOKE** (historical, retained): 5s, 5 iters/s, 25 reqs, 0% failures, 0 unhandled 5xx, p95 72.49 ms, p99 90.01 ms, max RSS 103.18 MiB.
- **FULL RED baseline (authentic, preserved before remediation):** 2,000 it/s × 60s, 32 nodes, SQLite. 5,949 completed reqs (~66.03 req/s), 112,551 dropped, p95 50.14s, p99 58.04s, `http_req_failed` 55.45%, custom unhandled 5xx metric 0% (0/5949) but widespread connection refusals/unavailability under overload, MAX_RSS 316.03 MiB, k6 exit 99, thresholds crossed. Evidence: `story-3.5-full-red-*` / originals.
- **Diagnosis:** global `write_lock` + synchronous per-event durable DB commit path (multi-statement transaction per heartbeat), downsampler as post-commit in-memory projection only (no persistence reduction), SQLite write serialization/contributing contention. Async/batched persistence preserving canonical ack semantics not implemented; frozen spec forbids lossy batching (tension documented). `docs/story-3-5-nfr-bottleneck-analysis.md`.
- **Safe remediation:** SQLite WAL/busy_timeout/synchronous=NORMAL tuning (`adapters/db/engine.py`); diagnostic ramp support in NFR harness (formal profiles unchanged). No threshold/contract weakening.
- **Ramp diagnostics:** canonical saturation ~71–78 req/s (100–1000 targets, 10s); failures escalated at 500+. No credible 2,000 req/s capacity. `evidence/impl2/nfr/story-3.5-ramp-analysis.md`.
- **Formal FULL retest:** NOT rerun (Step 9 precondition unmet). Verdict: **FAIL for formal NFR gate / CONCERNS for functional correctness**. Do not claim PASS.
- **PostgreSQL comparison:** PostgreSQL 17.11 used the same canonical route and frozen synchronous/atomic contract. Canonical throughput peaked at 20.57 responses/s; the 2,000 target dropped 10,095 iterations and failed 97.63% of HTTP requests. PostgreSQL FULL was not run because the diagnostic gate failed. Both backend results remain separately RED.

### Story 3.6
- Backend maintenance integration: `test_story_3_6_maintenance.py` PASS.
- Playwright (real backend, `trace: 'on-first-retry'`, no retries used, no intentional failure): `npx playwright test` — **1 passed, 0 failed, 0 skipped**. `FleetMapPage` POM + `tests/e2e/story-3.6-maintenance-drain.spec.ts`. Verified 32-node grid, server selection, drain start, DRAINING/unavailable, idempotent reuse, typed `ERR_IDEMPOTENCY_CONFLICT` (409), workload completion -> MAINTENANCE/unavailable. Evidence: `evidence/impl2/playwright/playwright-results.xml`.

## C. Time invested + TLOC using Git (actual data only)

- No elapsed engineering time inferred from timestamps.
- Recent commit timestamps (`git log --format="%h|%ad|%s" --date=iso --max-count=12`): `7ce0f49 2026-11-07 14:12:38 -0500`, `1f494bf 14:11:59`, `660e5a2 14:11:44`, `e28c43d 14:11:37`, `cbe87f0 13:08:10`, `ac74093 13:07:57`, `7e21c79 13:07:53`, `ce1c634 13:07:42` (Impl-2), plus prior Impl-1 fixes `3abc6f2`–`cced9c1`.
- Branch commits ahead of baseline in recent history represent implementation/test/docs work for 3.4–3.6 (see git log). `git diff --stat` / `--numstat` at continuation start of quality fixes showed 10 files, +52/-24 (ruff/governance hygiene edits). Additional continuation edits in this run (traceability/NFR/sprint/AI log/presentation, coverage/playwright evidence dirs, migration test hygiene) are uncommitted; use `git diff --stat`/`--numstat` after review for exact TLOC. Do not invent hours.

## D. Teamwork / validation / partner interaction

- Team: Mariana De La Cruz and Julian Motta.
- Human validation decisions recorded in `docs/ai-decision-log-impl2.md` (>=8 entries, >=2 MODIFY/REJECT; includes canonical-contract precedence, ATDD flow, non-lossy downsampling design, LOCAL_SMOKE vs FULL truthfulness, real-backend Playwright/no hard waits, and proper Windows test-environment classification/fix).
- Validation performed: full pytest baseline with basetemp, branch coverage >=90% core-domain evidence, ruff check/format, project-owned hardcoded sleep/timeout scan, Playwright E2E real run, NFR assessment with explicit profile distinction. Sprint status and traceability updated truthfully (`test/traceability-matrix.md`).
- Story 3.5 formal NFR remains unmet after authentic RED + diagnosis + safe tuning + ramp: current synchronous SQLite architecture shows no credible 2,000 req/s capacity. Full PASS would require deeper contract-safe redesign (durable async/batched semantics reconciled with frozen spec/contracts) and/or a separately labeled backend profile with authentic evidence; thresholds must not be relaxed.
