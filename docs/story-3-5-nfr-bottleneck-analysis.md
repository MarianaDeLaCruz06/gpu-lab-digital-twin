# Story 3.5 NFR Bottleneck Analysis (2026-11-07)

## Scope

Diagnostic analysis of the authentic FULL RED run and the current implementation path for `POST /v1/nodes/{nodeId}/heartbeats` (Story 3.5). Evidence is taken from preserved RED artifacts, source inspection, and a local in-process micro-benchmark. No metrics are fabricated.

## RED baseline evidence (preserved)

- `evidence/impl2/nfr/story-3.5-full-red-summary.md`
- `story-3.5-full-red-stdout.txt`, `story-3.5-full-red-stderr.txt`, `story-3.5-full-red-k6.txt`, `story-3.5-full.db`

Key RED metrics: 2,000 it/s target × 60s; 5,949 completed requests (~66.03 req/s); 112,551 dropped iterations; `http_req_duration` avg 15.93s, p95 50.14s, p99 58.04s; `http_req_failed` 55.45% (3,299/5,949); `unhandled_server_error_rate` 0.00% (0/5,949 by custom 5xx metric); 2,000 VUs reached with `Insufficient VUs`; k6 exit 99. Stderr shows widespread `connectex ... target machine actively refused` under overload.

## Implementation path inspected

- `tests/nfr/telemetry-storm.js`, `scripts/run-story-3-5-nfr.ps1`
- `src/gpu_lab_twin/api/routes/telemetry.py` — `def ingest_heartbeat` (sync FastAPI route) calls `container.heartbeats.ingest_heartbeat(...)`.
- `src/gpu_lab_twin/application/heartbeat_service.py` — acquires **process-wide** `threading.Lock` (`write_lock`, AD-1) for the whole ingest decision path; validates, loads node, checks idempotency/ordering/boot succession, computes decision/explanation, calls `commit_heartbeat`; **after commit** observes `TelemetryDownsampler` in memory (no DB persistence reduction).
- `src/gpu_lab_twin/adapters/db/node_repository.py` — `commit_heartbeat` opens one SQL transaction (`session.begin()`): CAS update on `nodes` (`_compare_and_set`), append telemetry snapshot (`select max(ingest_offset)`, conditional `update ... is_current=false`, insert snapshot, `flush`, insert GPU samples), optional state history insert, close/open alerts (select/update/upsert), audit insert. One transaction per accepted heartbeat.
- `src/gpu_lab_twin/domain/telemetry_downsampling.py` — bounded in-memory fixed-window (100 ms) projection, peak-preserving; **secondary projection only**.
- `src/gpu_lab_twin/adapters/db/engine.py` — SQLite uses `check_same_thread=False`; file DB previously had default journal/locking behavior (post-RED remediation added WAL/busy_timeout/synchronous=NORMAL pragmas; RED run predates that change).
- `src/gpu_lab_twin/bootstrap.py` — single `write_lock` shared by heartbeats, liveness, connectivity, maintenance; downsampler capacity `len(nodes)*600` windows.
- NFR script starts `uvicorn gpu_lab_twin.main:app --host 127.0.0.1 --port 8766` (single process, default workers) against SQLite file DB.

## Answers to required diagnostic questions

1. **DB transactions per heartbeat (accepted/apply path):** 1 application transaction per accepted heartbeat (`commit_heartbeat` does all writes inside `session.begin()`). Rejected/idempotent paths may do reads/lookups and separate small commits as coded (e.g., ignored heartbeat commit path has its own transaction). Under ideal valid load, ~1 write transaction per applied event.
2. **DB rows/writes per applied heartbeat (typical):** node CAS `UPDATE` (1) + telemetry snapshot `INSERT` (1) + GPU sample `INSERT`s (1 per sample; workstation has 1 GPU, server has 2) + optional `node_state_history` `INSERT` (only when state/cordon transition) + alert close `UPDATE`s / upsert `INSERT...ON CONFLICT` (depends on observed/closed reasons) + audit `INSERT` (1). Also supporting DML/queries in the same transaction: `SELECT max(ingest_offset)` and conditional `UPDATE telemetry_snapshots SET is_current=false` for the node. **No single fixed count** without workload mix; a steady healthy workstation heartbeat is still several statements/rows, not 1.
3. **Is each raw telemetry event synchronously persisted?** **Yes.** `HeartbeatService` calls `self._nodes.commit_heartbeat(...)` before returning; repository performs synchronous SQL commit in the request path. Downsampler is observed after commit as an in-memory projection only.
4. **Does the downsampler reduce persistence work or only maintain an additional projection?** **Only an additional bounded in-memory projection.** It does not replace, batch, or reduce telemetry/history/audit persistence.
5. **Is SQLite write serialization the dominant bottleneck?** **Major contributor, combined with per-event synchronous transaction cost and global serialization.** SQLite allows one writer at a time; per-heartbeat multi-statement transactions amplify lock/commit overhead. A post-RED local in-process micro-benchmark (same node, valid succession, file SQLite, after WAL/NORMAL pragma change) achieved ~138 req/s sequentially for 300 events — far below 2,000 req/s and consistent with the RED run’s ~66 req/s under real HTTP/32-node/load contention.
6. **Is the request holding a DB transaction while doing non-DB work?** The DB transaction is scoped to repository commit methods (`session.begin()`), not held across the full service method. However, the service holds the **global `write_lock`** across read/decision/commit, so DB latency serializes all heartbeat ingestion globally.
7. **Is the application using one blocking synchronous path for all ingestion?** **Yes.** Sync FastAPI handler -> sync service -> global `threading.Lock` -> sync SQLAlchemy/SQLite commit. Uvicorn runs sync handlers in a threadpool, but the global lock and DB serialization create a single effective ingestion bottleneck.
8. **Why did the API become connection-refused under pressure?** RED stderr shows `dial tcp 127.0.0.1:8766 connectex ... target machine actively refused` during overload. With extreme request latency/backlog (p95 50s) and high arrival rate, listening/backlog/worker capacity is exhausted and new connections fail. This is **service saturation/exhaustion under pressure**, not successful handling. The custom `unhandled_server_error_rate` measured 0.00% for responses it classified as server 5xx (0/5,949), but `http_req_failed` was 55.45% overall — connection failures dominate client-side failure accounting.
9. **Did the API process crash/restart, or simply exhaust connection/worker capacity?** Evidence indicates **exhaustion/capacity saturation** (connection refused, massive drops, very high latency) rather than a clean handled 5xx crash pattern. The NFR script samples RSS for server PIDs; RED reported MAX_RSS 316.03 MiB (above <200 MB target in that run) and k6 exit 99 due to threshold crossings. No evidence in captured summary of an orderly crash loop, but full server stdout/stderr beyond script capture would be needed for absolute certainty.
10. **Actual sustainable throughput before changes (measured):** RED achieved **~66.03 req/s** completed over the full profile. Local in-process sequential micro-benchmark (post-WAL pragma change, file SQLite, 300 applied heartbeats, same node): **~138.4 req/s**. Both are << 2,000 req/s; real HTTP + 32 nodes + contention explains lower RED throughput.

## Classification

| Class | Assessment |
|---|---|
| APPLICATION ARCHITECTURE BOTTLENECK | **Primary.** Global `write_lock` + synchronous per-event full persistence path + downsampler not reducing persistence. |
| SYNCHRONOUS PERSISTENCE BOTTLENECK | **Primary.** Every heartbeat durably committed synchronously before response. |
| SQLITE WRITE-CONTENTION LIMIT | **Contributing/measured factor.** Single-writer serialization and per-transaction overhead on SQLite; 138 rps micro-benchmark still far below 2,000 rps. Not sufficient alone to dismiss, but real. |
| WEB-SERVER/WORKER BOTTLENECK | **Contributing under saturation.** Single-process uvicorn + threadpool blocked behind global lock/DB; connection refusal at 2,000 it/s arrival. |
| LOAD-GENERATOR LIMIT | **Minor/secondary signal.** k6 reported insufficient VUs at 2,000 VUs, but the dominant issue is server-side inability to sustain throughput (66 req/s, 50s p95). |
| TEST DESIGN DEFECT | **No.** The formal scenario matches stated Story 3.5 target; RED is a valid measurement. |

## Story 3.5 requirement check (critical)

The user remediation request states Story 3.5 requires “async/batched persistence”. The **frozen repo spec** (`docs/spec-3-5-telemetry-storm.md`) states: “Every heartbeat remains durably processed by the existing atomic repository path; a bounded pure-domain projection groups accepted metrics into 100 ms windows (10 Hz)…” and “Never: replace heartbeat persistence with lossy batching”. The current implementation matches the frozen spec’s durable-per-heartbeat approach but **does not implement a durable async/batched persistence pipeline** that also preserves canonical per-event semantics before acknowledgement. This is a **spec/requirement tension** that must not be resolved by silently weakening APPLIED/DUPLICATE/LATE/BOOT_CHANGE semantics, durability, or ordering/idempotency contracts.

## Post-RED safe remediation applied (no contract weakening)

- SQLite engine tuning for file DBs: `busy_timeout=30000`, `journal_mode=WAL` (best effort), `synchronous=NORMAL`, `timeout=30`. Legitimate local performance/reliability tuning; does not change domain contracts. RED evidence predates this change.

## Honest feasibility note

Achieving 2,000 req/s for 60s with **full per-event synchronous canonical semantics** (duplicate detection, ordering/idempotency, CAS, history/audit/alerts, durable commit before response) on a single-process SQLite deployment on this Windows machine is unlikely without deeper redesign and/or a PostgreSQL-backed formal profile. Any redesign must preserve externally agreed behavior and must be labeled by backend; PostgreSQL PASS cannot be reported as SQLite PASS.
