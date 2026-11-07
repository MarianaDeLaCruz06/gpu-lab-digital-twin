# Solu-2 Traceability Matrix

Phase 3 initial pass used `PENDING` Story IDs. Phase 4 final pass replaced every pending value after `planning/epics.md` was validated. Status `RED` means an executable contract test exists and currently fails at the intentional operation stub; `PLANNED` means the NFR evidence procedure is specified without fabricated runtime evidence.

Impl-2 continuation (2026-11-07, branch `feature/impl2`) adds assignment-story traceability below. Evidence paths are repository-relative. Statuses are truthful to executed evidence (LOCAL_SMOKE vs FULL_NFR distinguished).

| PRD FR/NFR | UX Scenario | AD-n | Contract Clause | Test ID | Story ID | Status |
|---|---|---|---|---|---|---|
| FR-1 Fixed fleet | Scenario 1 / Fleet Success, Empty | AD-4, AD-8 | ingest Q; I-H6 | HB-FRESH-001, fixture cardinality | 1.1 | RED |
| FR-2 Validation/ingestion | Scenario 1 / Error, Denied | AD-1, AD-8 | P-H1–H5; rejection non-effects | HB-FRESH-001, HB-INVALID-001, SC-ISOLATION-001 | 1.1, 1.2 | RED |
| FR-3 Ordering/idempotency | Scenario 1 | AD-1, AD-6 | P-H6/H7; I-H1/I-H2/I-H5 | HB-ORDER-001, HB-IDEM-001 | 1.2 | RED |
| FR-4 Silence | Scenario 4 | AD-2, AD-4 | I-H3; transition Q | HB-SILENCE-001 | 1.3 | RED |
| FR-5 Thermal | Scenario 2 | AD-3, AD-4 | ingest Q; I-H4/I-T2 | HB-THERMAL-001/002 | 2.1 | RED |
| FR-6 Reboot | Scenario 3 | AD-4, AD-6 | P-H3; I-H5/I-T6 | HB-REBOOT-001 | 2.2 | RED |
| FR-7 State evaluation | Scenarios 1–4 | AD-4 | transition Q; I-T1–T6 | ST-PRECEDENCE-001, ST-INVALID-001 | 1.3, 2.1, 2.2, 2.3, 3.1, 3.3 | RED |
| FR-8 Maintenance drain | Scenario 4 Maintenance | AD-1, AD-7, AD-8 | maintenance P/Q; I-M1–M3/M5 | MT-HAPPY-001, MT-INVALID-001, MT-CONC-001, MT-STALE-001, MT-EXPLAIN-001 | 3.1, 3.2 | RED |
| FR-9 Maintenance release | Maintenance Success/Denied | AD-4, AD-7 | I-M4; reducer precedence | ST-PRECEDENCE-001 | 3.3 | RED |
| FR-10 Flapping | Scenario 4 / stable card | AD-5 | transition Q; I-T4/I-T5 | ST-FLAP-001 | 2.3 | RED (P0) |
| FR-11 Fleet/node views | Fleet/Node Loading–Denied | AD-4, AD-8 | response DTOs; atomic exposure | HB-FRESH-001, ST-EXPLAIN-001 | 1.1, 4.1 | RED |
| FR-12 Explainability | All scenarios | AD-3–AD-7 | all Q; I-T3 | ST-EXPLAIN-001, HB-THERMAL-001, HB-REBOOT-001, MT-EXPLAIN-001 | 4.1 | RED |
| FR-13 Fault injection | Fault Injector / all scenarios | AD-2, AD-3, AD-5–AD-8 | Time clauses and inbound ports | mandatory HB/ST/MT suite | 4.2 | RED |
| NFR-1 Fleet completeness | Fleet Success/Empty | AD-8 | I-H6 | seed-fleet fixture assertions | 1.1 | PLANNED |
| NFR-2 Hardware independence | Fault Injector | AD-8 | ports purity | CI dependency scan | 1.1, 4.2 | PLANNED |
| NFR-3 Thermal safety | Scenario 2 | AD-3, AD-4 | I-H4/I-T2 | HB-THERMAL-001/002 | 2.1 | RED |
| NFR-4 Silence accuracy | Scenario 4 | AD-2 | I-H3 | HB-SILENCE-001 | 1.3 | RED |
| NFR-5 Idempotency | Scenario 1 / maintenance retry | AD-1, AD-7 | I-H1/I-M1 | HB-IDEM-001, MT-CONC-001 | 1.2, 3.2 | RED (P0) |
| NFR-6 Determinism | All scenarios | AD-4 | I-T1 | ST-PRECEDENCE-001 | 1.3, 4.3 | RED |
| NFR-7 Explainability | All scenarios | AD-3–AD-7 | I-T3 | ST-EXPLAIN-001 and explain tests | 4.1 | RED |
| NFR-8 Flapping containment | Scenario 4 | AD-5 | I-T4/I-T5 | ST-FLAP-001 | 2.3 | RED (P0) |
| NFR-9 Data integrity | Error/Denied | AD-1, AD-6, AD-8 | rejection non-effects; I-H2/H5/H6 | HB-ORDER-001, SC-ISOLATION-001 | 1.2, 4.3 | RED (P0 stale) |
| NFR-10 Mandatory scenarios | Scenarios 1–4 | AD-2–AD-8 | all three operations | full 18-test suite | 4.2 | RED |
| NFR-11 Exposure ordering/performance | Fleet Loading/Success | AD-1, AD-4 | all Q latency clauses | planned 32-concurrent-node evidence | 1.1, 3.1, 4.1 | PLANNED |
| NFR-12 Process-local boundary | Empty/Restart | AD-8 | non-claims and reset | planned restart evidence | 1.1, 4.3 | PLANNED |
| NFR-13 Precedence collisions | All state views | AD-3–AD-7 | I-T1/I-T2/I-M4 | ST-PRECEDENCE-001 | 2.1, 3.3, 4.3 | RED |

## AD coverage gate

| AD | RED test(s) that fail if rule is removed | Story/stories |
|---|---|---|
| AD-1 | HB-ORDER-001, HB-IDEM-001, MT-CONC-001 | 1.2, 3.2 |
| AD-2 | HB-SILENCE-001 | 1.3, 4.2 |
| AD-3 | HB-THERMAL-001/002 | 2.1, 4.1 |
| AD-4 | ST-PRECEDENCE-001, ST-INVALID-001 | 1.3, 2.1, 3.3, 4.1 |
| AD-5 | ST-FLAP-001 | 2.3, 4.1 |
| AD-6 | HB-ORDER-001, HB-REBOOT-001 | 1.2, 2.2 |
| AD-7 | MT-HAPPY-001, MT-CONC-001, MT-STALE-001 | 3.1, 3.2, 3.3 |
| AD-8 | SC-ISOLATION-001, MT-STALE-001 | 1.1, 3.1, 4.3 |

## Gate summary

- P0 requirement/risk → executable RED test → story: 4/4 (100%).
- AD-n → executable RED test → story: 8/8 (100%).
- FR/NFR orphans: 0. Story orphans: 0. Pending Story IDs: 0.
- Required contract-behavior test orphans: 0; all 18 RED tests map to an FR/NFR, AD, contract clause, or mandatory non-effect.

## Mandatory flapping end-to-end chain

`PRD FR-10 / NFR-8` → `UX Scenario 4 (stable card, no pulse/countdown)` → `AD-5` → `transitionNodeState Q, I-T4, I-T5` → domain enforcement at the `StabilityPolicy` port/reducer guard plus physical alert deduplication at `alerts_one_open_per_reason_uq` → P0 risk `R-01` → executable RED test `ST-FLAP-001` → dedicated Story `2.3`.

The unresolved ODD-5 baseline retains raw evidence, preserves public state/connectivity/cordon, emits zero flapping alerts, and maintains at most one unresolved-policy diagnostic. No hidden hysteresis value is introduced.

## Impl-2 assignment story traceability (2026-11-07 continuation)

| Assignment | Requirement / intent | Story / spec | ATDD RED evidence | Implementation | GREEN / verification tests | NFR / E2E evidence | Verdict |
|---|---|---|---|---|---|---|---|
| 3.4 Anti-flapping / hysteresis (maps canonical 2.3 / FR-10, NFR-8, AD-5) | Contain 5-second connectivity flapping without inventing unapproved numeric classifier; preserve canonical states, evidence-only unresolved policy, no flapping alert flood | `docs/spec-3-4-anti-flapping-hysteresis.md`, `_bmad-output/test-artifacts/atdd-checklist-3-4-anti-flapping-hysteresis.md` | `evidence/impl2/atdd/story-3.4-red.txt` (authentic RED at missing connectivity seam) | `src/gpu_lab_twin/domain/connectivity_policy.py`, `src/gpu_lab_twin/application/connectivity_service.py`, related ports/adapters/UI exposure per impl | `tests/acceptance/test_story_3_4_connectivity_flapping.py`, `tests/unit/test_connectivity_policy.py` PASS; full regression 147 passed (2026-11-07 continuation, basetemp) | N/A (functional/safety story) | PASS (green, anti-flapping behavior verified) |
| 3.5 Telemetry storm downsampling | Handle 32-node storm; bounded memory; 10 Hz windowed output; peak GPU temperature preserved within <=1%; formal 2,000 events/s for 60s, 0 unhandled 5xx, RSS < 200 MB | `docs/spec-3-5-telemetry-storm.md`, `docs/story-3-5-nfr-bottleneck-analysis.md` | Flow D NFR RED baseline preserved (authentic): `evidence/impl2/nfr/story-3.5-full-red-*` | `src/gpu_lab_twin/domain/telemetry_downsampling.py`, `src/gpu_lab_twin/application/heartbeat_service.py`, `src/gpu_lab_twin/bootstrap.py`, `src/gpu_lab_twin/adapters/db/engine.py` (SQLite WAL/busy_timeout/synchronous tuning, safe) | `tests/unit/test_telemetry_downsampling.py`, `tests/integration/test_story_3_5_telemetry_storm.py` PASS; full regression 147 passed, 0 failed/errors/skipped, 95% branch coverage | LOCAL_SMOKE PASS (historical). **FULL RED (authentic):** 2,000 it/s×60s, 5,949 reqs (~66.03 req/s), 112,551 dropped, p95 50.14s, p99 58.04s, `http_req_failed` 55.45%, custom unhandled 5xx metric 0% but massive connection refusals/unavailability, MAX_RSS 316.03 MiB, thresholds crossed. **Ramp diagnostics:** `evidence/impl2/nfr/story-3.5-ramp-analysis.md` — canonical saturation ~71–78 req/s, no credible 2,000 req/s capacity. **Formal FULL retest NOT rerun** (no credible capacity). Summary: `evidence/impl2/nfr/story-3.5-summary.md`. | **FAIL (formal NFR) / CONCERNS (functional correctness)** — RED evidence preserved; architecture/synchronous persistence bottleneck diagnosed; safe tuning applied; full formal gate unmet; do not claim PASS |
| 3.6 Visual fleet drain orchestration (maps Epic 3 maintenance intent) | 32-node Fleet Grid; start maintenance drain; show DRAINING/maintenance-in-progress; simulated active workload completion -> MAINTENANCE; unavailable for new work; repeated request no duplicate locks; conflicting action shows typed error | `docs/sprint-status.yaml` assignment `3.6-visual-fleet-drain-orchestration`, UI + maintenance API implementation on branch | N/A (implementation/E2E continuation; existing feature tests) | `src/gpu_lab_twin/application/maintenance_service.py`, `src/gpu_lab_twin/api/routes/maintenance.py`, `src/gpu_lab_twin/api/routes/ui.py`, domain/ports/adapters, maintenance migration/models | `tests/integration/test_story_3_6_maintenance.py` PASS; full regression PASS | Playwright E2E (real backend via `playwright.config.ts` webServer): `tests/e2e/story-3.6-maintenance-drain.spec.ts` + `tests/e2e/pages/FleetMapPage.ts` POM. Run 2026-11-07: **1 passed, 0 failed, 0 skipped, 0 retries used**; evidence `evidence/impl2/playwright/playwright-results.xml`, `evidence/impl2/playwright/test-results/.last-run.json`. Verifies 32-node grid, server-gpu-01/central-gpu-server selection, drain start, DRAINING + unavailable, idempotent reuse (200), typed conflict `ERR_IDEMPOTENCY_CONFLICT` (409), workload completion -> MAINTENANCE. `trace: 'on-first-retry'` configured; no retry occurred so no trace.zip manufactured. | PASS (backend + real-browser workflow verified) |

**Unmapped Impl-2 requirements (3.4-3.6):** 0. Story 3.5 retains a formal FULL_NFR evidence gap (execution not possible in current environment) — this is recorded as CONCERNS, not a missing trace link.
