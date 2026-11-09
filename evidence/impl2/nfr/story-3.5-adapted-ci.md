# Story 3.5 — adapted formal NFR gate (CI evidence)

- Run: GitHub Actions `ci` run 42561772122, job `nfr-k6` (check run 128979543181), commit `151da54`, `ubuntu-latest`, SQLite file database, single uvicorn process.
- Script: `tests/nfr/telemetry-storm.js` with `K6_PROFILE=adapted` (32 nodes x 1 heartbeat/s, constant arrival, 60 s). Gate defined in `docs/spec-3-5-telemetry-storm.md` (Renegotiation 2026-11-08, I2-DL-15).
- The numbers below are copied verbatim from the job's annotations, which `.github/workflows/ci.yml` writes from `k6-adapted-summary.json` and `rss-kb.txt`. The full JSON is in the job's `k6-nfr` artifact.

```
notice Story 3.5 adapted k6 | requests=1921 rate=32.0/s p95=8.2ms p99=10.6ms max=40.5ms failed=0.0000 dropped=0
notice Story 3.5 RSS | peak 84.0 MiB over 65 samples (limit 200 MiB)
```

| Metric | Threshold | Result | Verdict |
|---|---|---|---|
| Requests / rate | 32 events/s x 60 s | 1,921 requests, 32.0/s | PASS |
| p95 latency | < 250 ms | 8.2 ms | PASS |
| p99 latency | < 500 ms | 10.6 ms | PASS |
| Failed requests (only 200/typed 409 count as handled) | 0 | 0.0000 | PASS |
| Dropped iterations | 0 | 0 | PASS |
| Unhandled 5xx / checks | 0 / 100% | thresholds held (k6 exit 0) | PASS |
| Peak service RSS | < 200 MB | 84.0 MiB | PASS |

The Annex `full` profile (2,000 events/s) was not rerun and its RED evidence is unchanged (`story-3.5-full-red-*`, `story-3.5-postgres-ramp-summary.md`).
