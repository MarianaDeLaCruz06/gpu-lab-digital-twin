---
title: 'Story 3.5 Telemetry Flood Ingestion Storm and Downsampling Pipeline'
type: 'feature'
created: '2026-11-07'
status: 'in-progress'
route: 'dispatch'
review_loop_iteration: 0
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
- [ ] Add pure downsampling policy and boundary/peak tests.
- [ ] Wire accepted heartbeat samples without changing persistence semantics.
- [ ] Add HTTP integration/burst tests and formal k6 quality gate.
- [ ] Execute supported profile and capture authentic metrics/RSS evidence.

**Acceptance Criteria:**
- Given valid high-rate heartbeats, when samples share a 100 ms window, then output is at most 10 Hz and maximum GPU temperature error is at most 1%.
- Given sustained input, when capacity is exceeded, then memory remains bounded without dropping canonical heartbeat effects.
- Given the FULL profile, when 2,000 requests/s run for 60 seconds, then the formal gate records zero unhandled 5xx and service responsiveness; local smoke is reported separately.

## Implementation Notes

The Annex downsampling requirement is implemented as a secondary metric projection because binding FR-2/FR-3 require each heartbeat to retain its own event semantics.

## Spec Change Log

## Review Triage Log

## Verification

**Commands:**
- `uv run pytest tests/unit/test_telemetry_downsampling.py tests/integration/test_story_3_5_telemetry_storm.py` -- all pass.
- `k6 run tests/nfr/telemetry-storm.js` -- chosen profile produces authentic HTTP metrics.

