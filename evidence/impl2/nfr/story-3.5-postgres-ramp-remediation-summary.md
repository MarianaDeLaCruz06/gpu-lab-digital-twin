# Story 3.5 PostgreSQL Diagnostic Ramp Summary — Final Concurrency Spike (remediation v2, new evidence)

Executed 2026-11-08 against PostgreSQL 17.11 at `localhost:55432` (`gpu-lab-digital-twin-db-nfr`), using the canonical heartbeat route on `feature/story-3.5-nfr-remediation` with: async HTTP waiting (`await asyncio.wrap_future`, ack-after-commit preserved), fixed real batch collection window (collect after first item; previous 2ms behavior was idle-poll only), 20ms collection window / max batch 64 for this ramp, and writer instrumentation. PostgreSQL reset by harness before each run. **Does not overwrite** pre-remediation `story-3.5-postgres-ramp-*` artifacts.

Artifacts: `story-3.5-postgres-ramp-remediation-{100,250,500,1000,1500,2000}-{k6,stdout,stderr}.txt`.

| Target rps | http_reqs completed | Achieved http rps | Canonical responses | Canonical rps | Dropped | HTTP failed | Unhandled 5xx | p95 (http_req_duration) | p99 | Max RSS | Exit |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 | 453 | 32.93 | 453 | 32.93 | 547 | 0.00% | 0.00% | 6.15 s | 6.28 s | 131.77 MiB | 0 |
| 250 | 827 | 37.33 | 827 | 37.33 | 1,673 | 0.00% | 0.00% | 12.41 s | 12.51 s | 162.96 MiB | 0 |
| 500 | 1,306 | 36.18 | 1,306 | 36.18 | 3,695 | 0.00% | 0.00% | 27.24 s | 27.42 s | 212.67 MiB | 0 |
| 1,000 | 2,815 | 70.23 | 1,386 | 34.58 | 6,353 | 50.87% (1,432/2,815, transport/connection refused) | 0.00% | 32.96 s | 36.09 s | 308.11 MiB | 0 |
| 1,500 | 5,876 | 146.40 | 1,349 | 33.61 | 7,276 | 77.11% (4,531/5,876, transport) | 0.00% | 30.47 s | 36.06 s | 403.58 MiB | 0 |
| 2,000 | 11,100 | 276.20 | 1,264 | 31.45 | 6,528 | 88.71% (9,847/11,100, transport) | 0.00% | 26.74 s | 35.19 s | 445.64 MiB | 0 |

At 1000+ rps, transport failures (`connectex` connection refused to `127.0.0.1:8766`) dominated; `unhandled_server_error_rate` remained 0.00% (no observed HTTP 5xx responses).

## Comparison

- Pre-remediation PostgreSQL peak canonical: **20.57 rps**.
- Batch remediation v1 peak: **24.29 rps** (~1.18× vs original).
- Final concurrency spike peak: **37.33 rps** at 250 rps target (~**1.81×** vs original, ~**1.54×** vs v1). Still **< 50 rps** (hard keep/discard gate).

Improvement is real but not material by spike criteria. 500 rps sustained 0% HTTP failures with 1,306 canonical responses (36.18 rps), but 1000+ still showed transport saturation and 2000 rps produced only 31.45 canonical rps with 88.71% transport failures — **no credible capacity for formal 2,000 events/s × 60s FULL**.

## Phase 1 diagnosis (why prior production batches were small)

`DurableHeartbeatBatchWriter` previously waited `flush_timeout_s` only when the queue was empty, then drained `get_nowait()` after the first item — no collection window after first arrival. Under load this yields frequent batches of 1. Fixed by collecting for `collect_window_s` after the first item (configurable). Production ramp batch-size stats were not exported from the separate server process in this run (instrumentation added: `BatchWriterStats`); deterministic tests confirm multi-command batching/transaction reduction.

## Decision

**Conditional FULL not run.** Formal Story 3.5 NFR remains unmet. Safe low-risk fixes (async wait, real batching window) improved canonical throughput to ~37 rps peak but below the <50 rps stop/discard threshold for material performance remediation. Deeper Phase 3 redesign (concurrent cross-node preparation, optimistic validation, narrower global critical section beyond writer-thread serialization) was not implemented due to semantic risk and the hard gate; see spike report.
