# Story 3.5 NFR Summary (2026-11-07)

## Baseline (RED, preserved)
- Formal FULL profile executed authentically: 2,000 it/s × 60s, 32 nodes, SQLite, single-process uvicorn (`scripts/run-story-3-5-nfr.ps1 -Profile full`).
- **Result:** 5,949 completed requests (~66.03 req/s), 112,551 dropped iterations, `http_req_duration` avg 15.93s / p95 50.14s / p99 58.04s, `http_req_failed` 55.45%, `unhandled_server_error_rate` 0.00% (custom 5xx metric, 0/5949), 2,000 VUs reached + insufficient VUs, widespread connection refused under overload, MAX_RSS 316.03 MiB, k6 exit 99. Thresholds crossed: `dropped_iterations`, `http_req_duration p(95)<5000`.
- Preserved: `evidence/impl2/nfr/story-3.5-full-red-summary.md`, `story-3.5-full-red-stdout.txt`, `story-3.5-full-red-stderr.txt`, `story-3.5-full-red-k6.txt` (originals also retained).

## Diagnosis
- Primary bottleneck: **application architecture + synchronous per-event persistence** under global `write_lock` (AD-1), with SQLite write serialization/contributing contention. Each accepted heartbeat performs a synchronous multi-statement DB transaction (CAS, telemetry snapshot, max ingest offset + is_current handling, GPU samples, optional history, alerts, audit). Downsampler is a post-commit in-memory projection only (no persistence reduction). Async/batched persistence that preserves canonical semantics before ack is **not implemented**; frozen spec requires durable atomic processing and forbids lossy batching — requirement/spec tension documented in `docs/story-3-5-nfr-bottleneck-analysis.md`.
- Sustainable throughput evidence: RED ~66 req/s; post-tuning in-process micro-benchmark ~138 req/s; ramp diagnostics show successful/canonical saturation ~71–78 req/s with escalating latency/drops/failures.

## Remediation (safe, no contract weakening)
- SQLite engine tuning for file DBs: `busy_timeout=30000`, `journal_mode=WAL` (best effort), `synchronous=NORMAL`, connect timeout 30 (`src/gpu_lab_twin/adapters/db/engine.py`).
- Diagnostic harness extensions (defaults preserved): `tests/nfr/telemetry-storm.js` + `scripts/run-story-3-5-nfr.ps1` support `ramp` profile / `RAMP_RATE` / `RAMP_DURATION` for non-formal diagnostics.
- No duplicate public endpoint added; canonical route preserved; ordering/idempotency/thermal/silence semantics unchanged; no sleeps; no threshold relaxation.

## Ramp (diagnostic)
- 100→1000 target req/s, 10s runs: canonical throughput saturated ~71–78 req/s; 500+ showed request/connection failures. `evidence/impl2/nfr/story-3.5-ramp-analysis.md`.
- **Formal FULL retest NOT re-executed**: architecture showed no credible capacity for 2,000 req/s × 60s (Step 9 precondition not met). Repeating FULL would likely reproduce RED without deeper redesign/contract renegotiation and/or a separately labeled backend profile.

## Verdict
**CONCERNS / FAIL for formal Story 3.5 NFR gate** (full 2,000 events/s × 60s, p95 < 5s, dropped_iterations==0, 0 unhandled 5xx, RSS < 200 MB under full load not demonstrated). Correctness (10 Hz, peak preservation, bounded projection, heartbeat semantic preservation in tests) and LOCAL_SMOKE remain evidenced; RED FULL baseline and diagnostics are authentically preserved. Do not claim PASS.

## PostgreSQL controlled comparison

PostgreSQL 17.11 on the canonical Compose configuration was measured separately at 100–2,000 target req/s. Canonical throughput peaked at 20.57 responses/s; at 2,000 target req/s, 10,095 iterations were dropped and 97.63% of completed requests failed at the transport layer. No unhandled HTTP 5xx were observed, but responsiveness failed decisively. The conditional PostgreSQL FULL run was not executed. Evidence: `story-3.5-postgres-ramp-summary.md` and per-rate artifacts.
