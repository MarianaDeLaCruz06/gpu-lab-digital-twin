# Story 3.5 Ramp Analysis (diagnostic, 2026-11-07)

All runs: `scripts/run-story-3-5-nfr.ps1 -Profile ramp -Rate <N> -Duration 10s` against local FastAPI/SQLite. **Post-RED tuning applied before these ramps:** SQLite engine pragmas `busy_timeout=30000`, `journal_mode=WAL` (best effort), `synchronous=NORMAL`, connect `timeout=30` for file DBs (`src/gpu_lab_twin/adapters/db/engine.py`). Single-process uvicorn as started by script. Profiles are **diagnostic only** — not substitutes for the formal FULL 2,000 req/s × 60s gate.

| Target req/s | Duration | Completed http_reqs / actual req/s | Canonical responses / s | Dropped iterations | http_req_failed | Unhandled 5xx (custom) | p95 http_req_duration | Notes |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 100 | 10s | 848 / 71.25/s | 848 / 71.25/s | 153 (12.86/s) | 0.00% (0/848) | 0.00% | 2.27s | 200 VUs max; insufficient VUs warning; saturated |
| 250 | 10s | 1109 / 76.16/s | 1109 / 76.16/s | 1392 (95.60/s) | 0.00% (0/1109) | 0.00% | 6.53s | 500 VUs; saturated |
| 500 | 10s | 2007 / 110.95/s | 1420? (see ramp stdout; 2007 reqs, 29.24% failed => ~1420 successful) | 2993 (165.45/s) | 29.24% (587/2007) | 0.00% | 12.51s | 1000 VUs; failures appear |
| 1000 | 10s | 7688 / 266.28/s | 2242 / 77.65/s | 2312 (80.08/s) | 70.83% (5446/7688) | 0.00% | 21.98s (all), 22.94s (expected_response) | 1928 VUs max; severe collapse; most requests failed (connection/request), successful canonical throughput ~78/s |

**Saturation point (evidence):** successful/canonical throughput saturates around **~71–78 req/s** in this architecture/configuration (SQLite + single-process uvicorn + global `write_lock` + synchronous per-event persistence, even after WAL/NORMAL tuning). Increasing arrival rate produces escalating latency, dropped iterations, and then large-scale request/connection failures — **not credible capacity** for 2,000 req/s sustained for 60s.

**Step 9 decision:** Formal FULL retest (2,000 req/s, 60s, 32 nodes) was **not re-executed** because architecture does not show credible capacity and would repeat the RED failure pattern without a deeper persistence/contract redesign (and possibly a different backend profile, which must be labeled separately).

**Artifact note:** Each ramp run overwrote `evidence/impl2/nfr/story-3.5-k6.txt` and `story-3.5-ramp-stdout/stderr/db`. Point-in-time summaries above were captured from run output; latest file reflects the final 1000 req/s diagnostic.
