---
stepsCompleted: ['step-01-load-context', 'step-02-define-thresholds']
lastStep: 'step-02-define-thresholds'
lastSaved: '2026-11-07'
inputDocuments:
  - planning/prd.md
  - planning/ARCHITECTURE.md
  - planning/detailed-design/contracts.md
  - docs/spec-3-5-telemetry-storm.md
  - evidence/impl2/nfr/story-3.5-k6.txt
  - .agents/skills/bmad-testarch-nfr/resources/knowledge/adr-quality-readiness-checklist.md
  - .agents/skills/bmad-testarch-nfr/resources/knowledge/ci-burn-in.md
  - .agents/skills/bmad-testarch-nfr/resources/knowledge/test-quality.md
  - .agents/skills/bmad-testarch-nfr/resources/knowledge/playwright-config.md
  - .agents/skills/bmad-testarch-nfr/resources/knowledge/error-handling.md
  - .agents/skills/bmad-testarch-nfr/resources/knowledge/playwright-cli.md
---

# Story 3.5 NFR Assessment

## Context and evidence availability

Implementation is available as the canonical heartbeat route plus a bounded 10 Hz peak-preserving projection. Evidence includes deterministic unit/integration tests and an authentic k6 LOCAL_SMOKE run against a migrated local FastAPI/SQLite service with process-tree RSS sampling. The formal FULL workload is represented in the same script but was not executed; conclusions must distinguish those profiles.

The binding NFR sources are the PRD, AD-1/AD-2/AD-8, the detailed heartbeat contract, and the Impl-2 Annex targets recorded in the Story 3.5 spec. Browser automation is `auto`; Playwright evidence is relevant to Story 3.6, while Story 3.5 relies on k6 and pytest.

## Declared NFR criteria

No separate test-design NFR plan exists, so thresholds come from the PRD, the approved Story 3.5 specification, and this run's explicit coverage target.

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

Recorded-only criteria: NFR-1 exact fleet cardinality (32 nodes/33 GPUs) and NFR-2 zero physical hardware are preserved in regression evidence but do not alter the four-domain audit gate.
