---
title: 'Story 3.5 Telemetry Flood Ingestion Storm and Downsampling Pipeline'
type: 'feature'
created: '2026-11-07'
status: 'in-progress'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '105236b31ef6940b336abf18a301ca565b48e4e6'
context: ['planning/ARCHITECTURE.md', 'planning/detailed-design/contracts.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A 32-node telemetry storm must not create an unbounded in-memory series or lose the canonical heartbeat liveness, ordering, and idempotency semantics.

**Approach:** Reuse `POST /v1/nodes/{nodeId}/heartbeats` unchanged. Every heartbeat remains durably processed by the existing atomic repository path; a bounded pure-domain projection groups accepted metrics into 100 ms windows (10 Hz) and retains each GPU's maximum temperature, making peak error zero at stored precision.

## Boundaries & Constraints

**Always:** Preserve AD-1/AD-2/AD-8, the canonical schema, 32 simulated nodes, deterministic time, bounded memory, zero unhandled 5xx in the NFR gate, and the formal 2,000 events/s for 60 seconds profile. Measure process RSS rather than estimating it.

**Never:** Add the Annex example route, replace heartbeat persistence with lossy batching, use an unbounded queue, touch physical hardware, silently weaken the full profile, or claim measurements that did not execute.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Window aggregation | Multiple samples for one GPU in 100 ms | One summary with maximum temperature and latest non-peak fields | N/A |
| Capacity boundary | More windows than configured capacity | Oldest summary is evicted; retained count never exceeds capacity | N/A |
| Heartbeat storm | Canonical valid requests across 32 nodes | Canonical APPLIED/ordered responses and bounded summaries | Typed contract errors; no unhandled 5xx |

</frozen-after-approval>

## Code Map

- `src/gpu_lab_twin/domain/telemetry_downsampling.py` -- pure fixed-window, peak-preserving bounded projection.
- `src/gpu_lab_twin/application/heartbeat_service.py` -- observes accepted heartbeats after the canonical atomic commit.
- `src/gpu_lab_twin/bootstrap.py` -- owns one bounded projection for the process.
- `tests/nfr/telemetry-storm.js` -- real HTTP FULL and LOCAL_SMOKE k6 profiles.
- `scripts/run-story-3-5-nfr.ps1` -- reproducible API/k6/RSS harness.

## Tasks & Acceptance

**Execution:**
- [x] Add pure downsampling policy and boundary/peak tests.
- [x] Wire accepted heartbeat samples without changing persistence semantics.
- [x] Add HTTP integration/burst tests and formal k6 quality gate.
- [x] Execute supported profile and capture authentic metrics/RSS evidence.
- [x] Verify PostgreSQL is an already-supported canonical backend using repository configuration, migrations, CI, tests, adapters, and documentation.
- [x] Start a reproducible local PostgreSQL environment using existing project infrastructure, or record a BLOCKED result if none is available.
- [x] Run PostgreSQL diagnostic ramps at 100, 250, 500, 1000, 1500, and 2000 requests/s, preserving separate `postgres` evidence and the unchanged synchronous/atomic contract.
- [x] Run the unchanged 2,000 requests/s for 60 seconds FULL profile only if the 2,000 requests/s ramp demonstrates credible capacity; preserve distinct PostgreSQL stdout, stderr, and summary evidence.
- [x] After any configuration or code changes, verify full pytest with no failures/errors/skips, Ruff, and branch coverage of at least 90%.

**Acceptance Criteria:**
- Given valid high-rate heartbeats, when samples share a 100 ms window, then output is at most 10 Hz and maximum GPU temperature error is at most 1%.
- Given sustained input, when capacity is exceeded, then memory remains bounded without dropping canonical heartbeat effects.
- Given the FULL profile, when 2,000 requests/s run for 60 seconds, then the formal gate records zero unhandled 5xx and service responsiveness; local smoke is reported separately.

## Implementation Notes

The Annex downsampling requirement is implemented as a secondary metric projection because binding FR-2/FR-3 require each heartbeat to retain its own event semantics.

The PostgreSQL comparison must use the same application contract, canonical route, and unchanged load thresholds. It must not wire the partial async batch writer, overwrite SQLite evidence, use an external/cloud database, or report SQLite PASS based on a PostgreSQL result. PostgreSQL FULL evidence paths are `evidence/impl2/nfr/story-3.5-postgres-full-stdout.txt`, `evidence/impl2/nfr/story-3.5-postgres-full-stderr.txt`, and `evidence/impl2/nfr/story-3.5-postgres-full-summary.md`.

## Spec Change Log

- 2026-11-07: Added deterministic fleet-validation and maintenance-precedence tests, raising core-domain branch coverage from 87.78% to 95.56%, and executed all six PostgreSQL diagnostic ramps without changing the synchronous/atomic heartbeat contract.
- 2026-11-07: Verified the existing canonical PostgreSQL implementation and recorded the validation as BLOCKED because the Docker daemon was unavailable; no PostgreSQL evidence files, ramps, FULL measurements, or unexecuted harness changes were retained or claimed.
- 2026-11-07: Verified the existing implementation and preserved the authentic FULL gate failure; no source-code changes were required in this resumed run.

## Review Triage Log

- 2026-11-07 RED: PostgreSQL ramps completed at 100, 250, 500, 1000, 1500, and 2000 requests/s. Canonical throughput peaked at 20.57 responses/s; the 2,000 rps ramp dropped 10,095 iterations and failed 97.63% of HTTP requests, so credible capacity was not demonstrated and the conditional PostgreSQL FULL profile was not run.
- 2026-11-07 BLOCKED: PostgreSQL ramp execution could not start because Docker Compose was installed but the local Docker daemon was unavailable. The required ramp task remains open. The conditional PostgreSQL FULL profile was correctly not run because no 2,000 requests/s ramp demonstrated credible capacity.
- 2026-11-07 BLOCKED: The formal 2,000 requests/s acceptance criterion remains RED. The frozen contract requires every heartbeat to complete the existing synchronous atomic repository path before acknowledgement, while the measured SQLite deployment sustains far less than the required rate. Further remediation requires an explicit architecture/contract decision (for example, a durable asynchronous ingest boundary or a different formal persistence backend); neither can be introduced without renegotiating the frozen contract.

## Verification

**Commands:**
- `uv run pytest tests/unit/test_telemetry_downsampling.py tests/integration/test_story_3_5_telemetry_storm.py` -- 7 passed.
- `uv run pytest` -- 147 passed.
- `k6 run tests/nfr/telemetry-storm.js` -- prior authentic FULL execution recorded 0 unhandled 5xx but failed the formal responsiveness gate: 5,949 completed requests, 112,551 dropped iterations, p95 50.14 s, maximum measured process-tree RSS 316.03 MiB, exit 99. LOCAL_SMOKE remains separate and passing.
- PowerShell parser plus `docker compose config --quiet` -- harness syntax and Compose configuration valid; Docker daemon unavailable for execution.
- `uv run --no-cache ruff check src tests migrations` and `uv run --no-cache ruff format --check src tests migrations` -- passed; 85 files already formatted.
- `uv run --no-cache pytest --cov=gpu_lab_twin --cov-branch --cov-report=term-missing` -- 147 passed, 0 failed/errors/skipped; repository-wide branch-aware coverage is 89%. A separate diagnostic excluding the intentionally unwired `heartbeat_batch_writer.py` measured 95%, but the exclusion is not used to claim the requested repository-wide threshold.
- `uv run pytest --cov=gpu_lab_twin --cov-branch --cov-report=term-missing` -- 154 passed, 0 failed/errors/skipped; package-wide branch-aware coverage is 90% and core-domain branch coverage is 95.56% (86/90).
- `scripts/run-story-3-5-nfr.ps1 -Profile ramp -Backend postgres ...` at 100, 250, 500, 1000, 1500, and 2000 requests/s -- all six diagnostic runs executed with separate PostgreSQL artifacts and zero HTTP 5xx. Canonical throughput peaked at 20.57 responses/s; PostgreSQL FULL was therefore not run.

