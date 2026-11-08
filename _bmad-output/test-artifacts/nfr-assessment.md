---
stepsCompleted: ['step-01-load-context', 'step-02-define-thresholds', 'step-03-gather-evidence', 'step-04-evaluate', 'step-05-gate-decision', 'step-06-red-remediation-ramp']
lastStep: 'step-06-red-remediation-ramp'
lastSaved: '2026-11-07'
inputDocuments:
  - planning/prd.md
  - planning/ARCHITECTURE.md
  - planning/detailed-design/contracts.md
  - docs/spec-3-5-telemetry-storm.md
  - docs/story-3-5-nfr-bottleneck-analysis.md
  - evidence/impl2/nfr/story-3.5-k6.txt
  - evidence/impl2/nfr/story-3.5-smoke-stdout.txt
  - evidence/impl2/nfr/story-3.5-full-red-summary.md
  - evidence/impl2/nfr/story-3.5-ramp-analysis.md
  - evidence/impl2/coverage/coverage.xml
  - test/traceability-matrix.md
---

# Story 3.5 NFR Assessment

## Context and evidence availability

Implementation uses the canonical heartbeat route plus a bounded 10 Hz peak-preserving in-memory projection (`domain/telemetry_downsampling.py`). **Per-event durable persistence remains synchronous** in the heartbeat path (atomic repository commit before response); async/batched persistence preserving canonical ack semantics is **not implemented**. The frozen spec requires durable atomic processing and forbids lossy batching; the user remediation request names async/batched persistence as a requirement — this tension is documented in `docs/story-3-5-nfr-bottleneck-analysis.md` and was **not** resolved by silently weakening contracts.

**Evidence profiles (never conflated):**
- **LOCAL_SMOKE (historical):** `story-3.5-k6.txt`/smoke artifacts — 5 iters/s, 5s, 25 reqs, 0% errors, 0 unhandled 5xx, p95 72.49ms, p99 90.01ms, max RSS 103.18 MiB.
- **FULL RED baseline (authentic, preserved):** `story-3.5-full-red-*` + originals — 2,000 it/s × 60s, 32 nodes, SQLite. 5,949 completed reqs (~66.03 req/s), 112,551 dropped, p95 50.14s, p99 58.04s, `http_req_failed` 55.45%, `unhandled_server_error_rate` 0.00% (custom 5xx metric), 2,000 VUs/insufficient VUs, connection refused under overload, MAX_RSS 316.03 MiB, k6 exit 99. Thresholds crossed.
- **RAMP diagnostics (post-tuning):** `story-3.5-ramp-analysis.md` — canonical throughput saturated ~71–78 req/s at 100–1000 target req/s; 500+ showed request failures. SQLite WAL/busy_timeout/synchronous=NORMAL tuning applied (`adapters/db/engine.py`). **No credible capacity** for 2,000 req/s × 60s.
- **PostgreSQL controlled ramps:** `story-3.5-postgres-ramp-summary.md` — PostgreSQL 17.11, canonical route and contract, 100–2,000 target req/s. Canonical throughput peaked at 20.57 responses/s; the 2,000 target dropped 10,095 iterations with 97.63% HTTP transport failures. PostgreSQL FULL was not run because credible capacity was absent.
- **Formal FULL retest:** **NOT RE-EXECUTED** (Step 9 precondition unmet; repeating would not be truthful progress).

## Declared NFR criteria

| Stable ID | Order | Domain | Exact declared label | Threshold | Threshold source |
|---|---:|---|---|---|---|
| performance-aggregate-telemetry-storm | 1 | Performance | aggregate telemetry storm | 2,000 events/s across 32 nodes for 60 seconds | docs/spec-3-5-telemetry-storm.md |
| performance-telemetry-output-frequency | 2 | Performance | telemetry output frequency | at most 10 Hz per windowed output | docs/spec-3-5-telemetry-storm.md |
| performance-process-memory-rss | 3 | Performance | process memory RSS | less than 200 MB | docs/spec-3-5-telemetry-storm.md |
| performance-peak-gpu-temperature-error | 4 | Performance | peak GPU temperature error | at most 1% | docs/spec-3-5-telemetry-storm.md |
| reliability-unhandled-server-error-rate | 5 | Reliability | unhandled server error rate | 0 | docs/spec-3-5-telemetry-storm.md |
| reliability-heartbeat-semantic-preservation | 6 | Reliability | heartbeat semantic preservation | every accepted heartbeat retains canonical ordering/idempotency/liveness effects | planning/detailed-design/contracts.md |
| reliability-decision-exposure-ordering | 7 | Reliability | decision exposure ordering | 100% atomic commit before fleet exposure; no numeric latency SLA | planning/prd.md (NFR-11) |
| maintainability-core-domain-branch-coverage | 8 | Maintainability | core domain branch coverage | at least 90% branch coverage | active IMPL-2 Run 2 requirement |

## Evidence gathered (2026-11-07)

| Evidence | Result |
|---|---|
| Downsampler/storm unit+integration tests | PASS (`test_telemetry_downsampling.py`, `test_story_3_5_telemetry_storm.py`). |
| Full regression | 147 collected, **147 passed, 0 failed, 0 errors, 0 skipped** (`--basetemp` approved path). |
| Branch coverage | **TOTAL 95%** (1781 stmts, 66 miss, 242 branches, 38 partial). Core domain: `telemetry_downsampling` 100%, `heartbeat_policy` 100%, `connectivity_policy` 100%, `maintenance` 96%, `explanation` 96%, `node_state` 94%, `fleet` 89%. >=90% target met. |
| LOCAL_SMOKE k6 | PASS for smoke profile (see above). |
| FULL RED k6 | **FAIL/RED** vs formal thresholds (see above); preserved as authentic evidence. |
| Ramp diagnostics | Saturation ~71–78 successful req/s; no credible 2,000 req/s capacity. |
| Ruff | `check .` and `format --check .` PASS. |

## Assessment by criterion

| ID | Assessment | Rationale |
|---|---|---|
| performance-aggregate-telemetry-storm | **FAIL (formal FULL RED)** | 66.03 req/s achieved, 112,551 dropped over 60s target. No credible capacity demonstrated post-tuning; formal retest not rerun. |
| performance-telemetry-output-frequency | **PASS** | 100 ms windows / 10 Hz verified by tests. |
| performance-process-memory-rss | **PASS (LOCAL_SMOKE) / FAIL (FULL RED)** | LOCAL_SMOKE 103.18 MiB; FULL RED MAX_RSS 316.03 MiB (>200 MB). |
| performance-peak-gpu-temperature-error | **PASS** | Peak/max temperature retained (0% at stored precision, <=1%). |
| reliability-unhandled-server-error-rate | **MIXED / FAIL overall** | Custom 5xx metric 0% in FULL RED, but `http_req_failed` 55.45% with massive connection refusals/drops indicates severe unavailability under load — formal reliability not met. |
| reliability-heartbeat-semantic-preservation | **PASS (functional tests)** | Canonical semantics preserved in implementation/tests; load-induced availability failure is separate from semantic correctness. |
| reliability-decision-exposure-ordering | **PASS (contract/regression)** | No numeric latency SLA; atomic commit/exposure discipline unchanged. |
| maintainability-core-domain-branch-coverage | **PASS** | >=90% core-domain branch coverage. |

## Gate decision

**Overall Story 3.5 NFR gate: FAIL (formal) / CONCERNS (functional correctness retained).** Do not mark done. Do not claim PASS. Both SQLite and PostgreSQL controlled measurements fail far below 2,000 req/s under the frozen synchronous per-heartbeat atomic persistence contract.
