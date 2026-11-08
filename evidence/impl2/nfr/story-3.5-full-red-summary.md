# Story 3.5 FULL NFR — RED (authentic baseline failure)

**Preserved:** 2026-11-07 (copied before any remediation rerun). Originals retained: `story-3.5-full-stdout.txt`, `story-3.5-full-stderr.txt`, `story-3.5-k6.txt`, `story-3.5-full.db`.

## Formal scenario (unchanged)

- Profile: `full` (`K6_PROFILE=full`, `scripts/run-story-3-5-nfr.ps1 -Profile full`)
- Target: 2,000 iterations/sec for 60 seconds, 32 simulated nodes
- Scenario: `constant-arrival-rate`, 1m0s, maxVUs 256–2000, gracefulStop 30s
- Backend: SQLite (`GPU_TWIN_DATABASE_URL=sqlite+pysqlite:///.../story-3.5-full.db`)

## Authentic result (RED)

| Metric | Value |
|---|---:|
| FULL executed | YES |
| Completed HTTP requests / iterations | 5,949 (`http_reqs`, `iterations`) |
| Achieved throughput | ~66.03 req/s (`66.034306/s`) |
| Dropped iterations | 112,551 (`1249.323784/s`) — threshold `count==0` **CROSSED** |
| `http_req_duration` avg / med / max | 15.93s / 0s / 59.65s |
| `http_req_duration` p(90) / p(95) / p(99) | 43.37s / **50.14s** / **58.04s** — threshold `p(95)<5000` **CROSSED** |
| `http_req_failed` | 55.45% (3,299 / 5,949) |
| Unhandled server error rate | **0.00%** (0 / 5,949) — custom metric reports no unhandled 5xx responses counted as server errors by the script metric |
| Checks | 11,898 total, 72.46% succeeded (8,622), 27.53% failed (3,276) |
| Canonical responses | 2,673 (`29.670482/s`) |
| VUs | reached 2,000 active VUs; k6 logged `Insufficient VUs, reached 2000 active VUs and cannot initialize more` |
| Max process-tree RSS (script) | 316.03 MiB (`MAX_RSS_BYTES` 331,378,688) |
| K6 exit code | 99 |
| Connection behavior | many `Request Failed` / `dial tcp 127.0.0.1:8766 ... connectex: target machine actively refused` under overload (see RED stderr) |

## Interpretation (evidence-based, pre-remediation)

- The formal 2,000 req/s for 60s target was **not met**: only ~66 req/s completed with massive iteration drops.
- Latency was extreme (p95 50.14s) and the service became connection-refused under pressure; the API was overwhelmed rather than returning handled 5xx for most failures.
- This is academically useful **Flow D RED NFR** evidence. It must not be overwritten or weakened to manufacture green.

## Files

- `story-3.5-full-red-stdout.txt`, `story-3.5-full-red-stderr.txt`, `story-3.5-full-red-k6.txt` (copied)
- `story-3.5-full-stdout.txt`, `story-3.5-full-stderr.txt`, `story-3.5-k6.txt`, `story-3.5-full.db` (original failing artifacts retained)
