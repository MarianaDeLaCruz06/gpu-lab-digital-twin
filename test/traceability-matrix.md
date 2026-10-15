# Solu-2 Traceability Matrix

Phase 3 initial pass used `PENDING` Story IDs. Phase 4 final pass replaced every pending value after `planning/epics.md` was validated. Status `RED` means an executable contract test exists and currently fails at the intentional operation stub; `PLANNED` means the NFR evidence procedure is specified without fabricated runtime evidence.

| PRD FR/NFR | UX Scenario | AD-n | Contract Clause | Test ID | Story ID | Status |
|---|---|---|---|---|---|---|
| FR-1 Fixed fleet | Scenario 1 / Fleet Success, Empty | AD-4, AD-8 | ingest Q; I-H6 | HB-FRESH-001, fixture cardinality | 1.1 | RED |
| FR-2 Validation/ingestion | Scenario 1 / Error, Denied | AD-1, AD-8 | P-H1–H5; rejection non-effects | HB-FRESH-001, HB-INVALID-001, SC-ISOLATION-001 | 1.1, 1.2 | RED |
| FR-3 Ordering/idempotency | Scenario 1 | AD-1, AD-6 | P-H6/H7; I-H1/H2/H5 | HB-ORDER-001, HB-IDEM-001 | 1.2 | RED |
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
