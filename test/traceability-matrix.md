# Solu-2 Traceability Matrix

Phase 3 initial pass used `PENDING` Story IDs. Phase 4 final pass replaced every pending value after `planning/epics.md` was validated. Status `RED` means an executable contract test exists and currently fails at the intentional operation stub; `PLANNED` means the NFR evidence procedure is specified without fabricated runtime evidence.

Impl-2 continuation (2026-11-07, branch `feature/impl2`) adds assignment-story traceability below. Evidence paths are repository-relative. Statuses are truthful to executed evidence (LOCAL_SMOKE vs FULL_NFR distinguished).

> **Reading note (2026-11-08):** the table below and the AD coverage gate are the **Solu-2 pre-implementation snapshot**. `RED` there means "executable contract test existed and failed at the stub before Impl-1"; it is not the current status. Current status, test files, CI evidence and verdicts are in **Impl-2 quality gate (current)** at the end of this file.

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

> Historical snapshot. The Story 3.5 verdict in this table (FAIL/CONCERNS) was superseded on 2026-11-08 by the adapted formal gate (I2-DL-15); see the current quality gate below.

| Assignment | Requirement / intent | Story / spec | ATDD RED evidence | Implementation | GREEN / verification tests | NFR / E2E evidence | Verdict |
|---|---|---|---|---|---|---|---|
| 3.4 Anti-flapping / hysteresis (maps canonical 2.3 / FR-10, NFR-8, AD-5) | Contain 5-second connectivity flapping without inventing unapproved numeric classifier; preserve canonical states, evidence-only unresolved policy, no flapping alert flood | `docs/spec-3-4-anti-flapping-hysteresis.md`, `_bmad-output/test-artifacts/atdd-checklist-3-4-anti-flapping-hysteresis.md` | `evidence/impl2/atdd/story-3.4-red.txt` (authentic RED at missing connectivity seam) | `src/gpu_lab_twin/domain/connectivity_policy.py`, `src/gpu_lab_twin/application/connectivity_service.py`, related ports/adapters/UI exposure per impl | `tests/acceptance/test_story_3_4_connectivity_flapping.py`, `tests/unit/test_connectivity_policy.py` PASS; full regression 147 passed (2026-11-07 continuation, basetemp) | N/A (functional/safety story) | PASS (green, anti-flapping behavior verified) |
| 3.5 Telemetry storm downsampling | Handle 32-node storm; bounded memory; 10 Hz windowed output; peak GPU temperature preserved within <=1%; formal 2,000 events/s for 60s, 0 unhandled 5xx, RSS < 200 MB | `docs/spec-3-5-telemetry-storm.md`, `docs/story-3-5-nfr-bottleneck-analysis.md` | Flow D NFR RED baseline preserved (authentic): `evidence/impl2/nfr/story-3.5-full-red-*` | `src/gpu_lab_twin/domain/telemetry_downsampling.py`, `src/gpu_lab_twin/application/heartbeat_service.py`, `src/gpu_lab_twin/bootstrap.py`, `src/gpu_lab_twin/adapters/db/engine.py` | `tests/unit/test_telemetry_downsampling.py`, `tests/integration/test_story_3_5_telemetry_storm.py` PASS; full regression 154 passed; package branch coverage 90%, core-domain 95.56% | SQLite FULL remains authentic RED. PostgreSQL 17.11 ramps: canonical peak 20.57 responses/s; at 2,000 target, 10,095 dropped and 97.63% HTTP failed; no credible FULL capacity. Evidence: `evidence/impl2/nfr/story-3.5-postgres-ramp-summary.md`. | **FAIL (formal NFR) / CONCERNS** — both backends fail the unchanged formal capacity gate; frozen synchronous atomic contract requires architecture decision |
| 3.6 Visual fleet drain orchestration (maps Epic 3 maintenance intent) | 32-node Fleet Grid; start maintenance drain; show DRAINING/maintenance-in-progress; simulated active workload completion -> MAINTENANCE; unavailable for new work; repeated request no duplicate locks; conflicting action shows typed error | `docs/sprint-status.yaml` assignment `3.6-visual-fleet-drain-orchestration`, UI + maintenance API implementation on branch | N/A (implementation/E2E continuation; existing feature tests) | `src/gpu_lab_twin/application/maintenance_service.py`, `src/gpu_lab_twin/api/routes/maintenance.py`, `src/gpu_lab_twin/api/routes/ui.py`, domain/ports/adapters, maintenance migration/models | `tests/integration/test_story_3_6_maintenance.py` PASS; full regression PASS | Playwright E2E (real backend via `playwright.config.ts` webServer): `tests/e2e/story-3.6-maintenance-drain.spec.ts` + `tests/e2e/pages/FleetMapPage.ts` POM. Run 2026-11-07: **1 passed, 0 failed, 0 skipped, 0 retries used**; evidence `evidence/impl2/playwright/playwright-results.xml`, `evidence/impl2/playwright/test-results/.last-run.json`. Verifies 32-node grid, server-gpu-01/central-gpu-server selection, drain start, DRAINING + unavailable, idempotent reuse (200), typed conflict `ERR_IDEMPOTENCY_CONFLICT` (409), workload completion -> MAINTENANCE. `trace: 'on-first-retry'` configured; no retry occurred so no trace.zip manufactured. | PASS (backend + real-browser workflow verified) |

**Unmapped Impl-2 requirements (3.4-3.6):** 0. Story 3.5's formal FULL_NFR profile was executed and is RED on both SQLite and PostgreSQL (see the gate below); this is a failed requirement, not a missing trace link.

## Impl-2 quality gate (current, 2026-11-08)

Chain required by the task: PRD requirement → user story → automated test files → CI evidence → verdict.
CI jobs (`.github/workflows/ci.yml`): **T** = `lint-and-test` (pytest on SQLite with coverage and on PostgreSQL 17, plus a migration round-trip); **E** = `e2e-playwright` (uploads `trace.zip`); **K** = `nfr-k6` (k6 smoke and adapted formal profile, plus the RSS < 200 MB assertion).
CI run 42561772122 (commit `151da54`): T, E and K all passed. Local run on 2026-11-08: pytest 437 passed / 0 failed / 0 skipped (346 unit, 85 integration, 6 acceptance); Playwright 1 passed; branch coverage 90% total, core domain 96–100%.

| PRD requirement | Assignment story (canonical) | Automated test files | CI evidence | Verdict |
|---|---|---|---|---|
| FR-1 fixed fleet, FR-2 validation/ingestion, FR-11 fleet view, NFR-1 completeness | 3.1 heartbeat ingestion (1.1) | `tests/integration/test_story_1_1_heartbeat_ingestion.py`, `tests/integration/test_fleet_view.py`, `tests/integration/test_health_probes.py`, `tests/unit/test_heartbeat_policy.py`, `tests/unit/test_fleet_inventory.py`, `tests/unit/test_domain_decision_tables.py` (capacity, GPU membership, receive-time tables) | T | PASS |
| FR-4 silence, NFR-4 silence accuracy (AD-2) | 3.2 silent node → OFFLINE (1.3) | `tests/integration/test_story_1_3_silent_node_detection.py`, `tests/integration/test_liveness_scan_wiring.py`, `tests/unit/test_silence_policy.py`, `tests/unit/test_scheduler.py`, `tests/unit/test_domain_decision_tables.py` (silence edge table) | T | PASS |
| FR-5 thermal, NFR-3 thermal safety (AD-3) | 3.3 thermal cordon (2.1) | `tests/integration/test_story_2_1_thermal_cordon.py`, `tests/unit/test_thermal_policy.py`, `tests/unit/test_domain_decision_tables.py` (88 °C edge on either GPU) | T | PASS |
| FR-7 state evaluation, NFR-6 determinism, NFR-13 precedence (AD-4) | 3.1–3.6 (shared reducer) | `tests/unit/test_node_state_reducer.py`, `tests/unit/test_domain_decision_tables.py` (complete 192-row reducer table) | T | PASS |
| NFR-2 hardware independence, NFR-9 data integrity (AD-1) | all | `tests/unit/test_architecture.py`, `tests/integration/test_revision_cas.py`, `tests/integration/test_migrations.py` | T | PASS |
| Concurrency defense: zero double allocation, exactly-once apply, gapless global order (AD-1, AD-7) | 3.5, 3.6 (and all writers) | `tests/integration/test_concurrency_hammer.py`; mutation evidence `evidence/impl2/concurrency/hammer-mutation-no-lock.txt` (fails without the lock) | T | PASS |
| FR-10 flapping, NFR-8 flapping containment (AD-5) | 3.4 anti-flapping (2.3) — Flow A | `tests/acceptance/test_story_3_4_connectivity_flapping.py`, `tests/unit/test_connectivity_policy.py`; RED `evidence/impl2/atdd/story-3.4-red.txt` | T | PASS |
| FR-2/FR-3 semantic preservation under storm; 10 Hz peak-preserving downsampling (≤ 1% peak error) | 3.5 telemetry storm — Flow D (functional) | `tests/unit/test_telemetry_downsampling.py`, `tests/unit/test_domain_decision_tables.py` (window bucketing), `tests/integration/test_story_3_5_telemetry_storm.py` | T | PASS |
| Story 3.5 NFR, adapted formal gate (I2-DL-15): 32 events/s × 60 s, p95 < 250 ms, p99 < 500 ms, 0 failed, 0 dropped, 0 unhandled 5xx, RSS < 200 MB | 3.5 telemetry storm — Flow D (capacity) | `tests/nfr/telemetry-storm.js` (`adapted` profile), `scripts/run-story-3-5-nfr.ps1 -Profile adapted` | K: p95 8.2 ms, p99 10.6 ms, 1,921 req, 0 failed, 0 dropped, RSS 84.0 MiB (`evidence/impl2/nfr/story-3.5-adapted-ci.md`) | PASS |
| FR-8 maintenance drain, FR-11 fleet view (AD-7); Annex badges Green → Amber → Blue; new work refused with 409 | 3.6 maintenance drain + fleet map — Flow E | `tests/integration/test_story_3_6_maintenance.py`, `tests/e2e/story-3.6-maintenance-drain.spec.ts`, `tests/e2e/pages/FleetMapPage.ts` | T, E (fresh `trace.zip` artifact); local trace `evidence/impl2/playwright/story-3.6-trace.zip` | PASS |

Requirements mapped to canonical backlog stories outside the six assignment stories, so not delivered in Impl-2: FR-3 full ordering contract (1.2; the ordering rules needed by 3.1 were implemented in Impl-1 B02), FR-6 reboot recovery (2.2), FR-9 maintenance release (canonical 3.3), FR-12/FR-13 and NFR-7/10/11/12 (Epic 4). Each is mapped to a story, so none is orphaned.

Story adaptations, each recorded as a human decision: 3.4 keeps the canonical states instead of inventing `FLAPPING_CORDONED` (I2-DL-01/02); 3.5 uses the adapted load gate instead of 2,000 events/s (I2-DL-15), and the 2,000 events/s RED evidence is kept unchanged; 3.6 shows the Annex alias `server-gpu-01` over the canonical `central-gpu-server`, and models "dispatch returns 409" as a typed `ERR_MAINTENANCE_CONFLICT` because Module 3 owns no dispatcher.

### Gate decision

| Check | Result |
|---|---|
| Assignment stories 3.1–3.6 mapped to tests and CI | 6/6 |
| Unmapped requirements | 0 |
| Functional acceptance (all six stories) | PASS |
| Flow A red phase documented | PASS (3.4) |
| Flow C test-after hardening | PASS (280 decision-table cases) |
| Flow D NFR: k6 latency/integrity/RSS gate | PASS (adapted formal profile, CI run 42561772122) |
| Concurrency defense (hammer + mutation proof) | PASS |
| Flow E POM, web-first assertions, no hard waits, trace | PASS (3.6) |
| Core-domain branch coverage ≥ 90% | PASS (96–100%) |
| Test pyramid 70/20/10 | PASS (78.8% unit / 19.4% integration / E2E kept to one journey) |

**Verdict: PASS.** Every requirement in scope maps to passing automated tests and CI evidence. The Story 3.5 capacity requirement passes under its formally adapted target (I2-DL-15). The Annex's original 2,000 events/s figure is not claimed. It remains documented RED evidence of the AD-1 design limit (`evidence/impl2/nfr/story-3.5-full-red-*`, `story-3.5-postgres-ramp-summary.md`).
