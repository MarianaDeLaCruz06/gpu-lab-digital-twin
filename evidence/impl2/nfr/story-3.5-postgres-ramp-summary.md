# Story 3.5 PostgreSQL Diagnostic Ramp Summary

Executed on 2026-11-07 against PostgreSQL 17.11 at `localhost:55432`, using the canonical synchronous/atomic heartbeat route. Each diagnostic used the unchanged 32-node request semantics and a 10-second constant-arrival-rate target. PostgreSQL was reset reproducibly with canonical Alembic downgrade/upgrade operations before each run.

| Target rps | Completed | Achieved rps | Canonical rps | Dropped | HTTP failed | Unhandled 5xx | p95 | p99 | Max RSS |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 | 340 | 20.57 | 20.57 | 661 | 0.00% | 0 | 10.87 s | 10.99 s | 124.57 MiB |
| 250 | 564 | 18.90 | 18.90 | 1,937 | 0.00% | 0 | 24.24 s | 24.27 s | 155.00 MiB |
| 500 | 215 | 5.36 | 5.36 | 3,950 | 0.00% | 0 | 37.29 s | 38.95 s | 204.55 MiB |
| 1,000 | 733 | 6.52 | 0.49 | 7,309 | 92.76% | 0 | 12.92 s | 17.42 s | 298.19 MiB |
| 1,500 | 2,266 | 56.35 | 4.30 | 9,892 | 92.67% | 0 | 14.77 s | 25.90 s | 397.40 MiB |
| 2,000 | 6,461 | 160.40 | 4.05 | 10,095 | 97.63% | 0 | 0 s* | 20.09 s | 454.36 MiB |

`*` Failed transport requests have zero-duration samples in k6, so the aggregate p95 at 2,000 rps is not evidence of healthy latency.

## Decision

PostgreSQL did not demonstrate credible 2,000 rps capacity. Canonical throughput peaked at 20.57 responses/s, below the historical SQLite saturation of approximately 71–78 canonical responses/s. The 2,000 target dropped 10,095 iterations and 97.63% of completed HTTP requests failed at the transport layer. The conditional 60-second FULL profile was therefore not executed.

Zero observed HTTP 5xx does not satisfy the formal responsiveness gate. The remaining bottleneck is the frozen synchronous, per-heartbeat atomic persistence contract and its request-per-transaction execution path; further tuning was stopped at the required decision gate.
