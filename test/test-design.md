# Solu-2 Risk-Based Test Design

Phase 3 roles: Julian Motta — Test Lead; Mariana De La Cruz — Reviewer. Scope is Module 3 only. Tests are executable RED contracts against explicit interface stubs; they do not implement production behavior.

## Risk register

Priority mapping: score 9 = P0; 6 = P1; 3–4 = P2; 1–2 = P3. The mandatory flapping risk is P0 by explicit project direction.

| ID | Risk | Probability 1–3 | Impact 1–3 | Score | Priority P0–P3 | Mitigating Contract | AD-n | Test Level |
|---|---|---:|---:|---:|---|---|---|---|
| R-01 | Five-second online/offline evidence causes public oscillation or alert flooding | 3 | 3 | 9 | P0 | transition Q; I-T4/I-T5 | AD-5 | Unit + contract |
| R-02 | Stale/out-of-order heartbeat overwrites newer state | 3 | 3 | 9 | P0 | ingest P-H7; I-H2 | AD-1, AD-6 | Unit + integration |
| R-03 | Duplicate heartbeat creates duplicate history/audit/events | 3 | 3 | 9 | P0 | ingest P-H6; I-H1 | AD-1 | Contract + integration |
| R-04 | Silence after more than three intervals is not detected or boundary fires early | 2 | 3 | 6 | P1 | ingest/transition I-H3 | AD-2 | Unit |
| R-05 | Temperature above 88°C remains eligible for new work | 2 | 3 | 6 | P1 | ingest Q; I-H4/I-T2 | AD-3, AD-4 | Unit + API |
| R-06 | Reducer accepts an invalid transition or violates precedence | 2 | 3 | 6 | P1 | transition P-T4; I-T1/I-T6 | AD-4 | Unit |
| R-07 | `ws-gpu-05` state loss does not enter `RECOVERING` or old epoch refills fields | 2 | 3 | 6 | P1 | ingest P-H3; I-H5/I-T6 | AD-6 | Unit + contract |
| R-08 | Concurrent/repeated maintenance drain creates duplicate lock/event | 3 | 3 | 9 | P0 | maintenance P-M4–M6; I-M1 | AD-1, AD-7 | Integration |
| R-09 | New work remains eligible after drain begins | 2 | 3 | 6 | P1 | maintenance Q; I-M2 | AD-4, AD-7 | API + integration |
| R-10 | Maintenance completes from stale/pre-lock/unknown workload facts | 2 | 3 | 6 | P1 | maintenance Q; I-M3 | AD-7, AD-8 | Unit + integration |
| R-11 | Automated decision omits rule IDs, evidence, observed value, or threshold/expected state | 2 | 3 | 6 | P1 | all Q; I-T3 | AD-3, AD-4 | Contract |
| R-12 | Invalid/unknown node telemetry mutates another node or leaks context | 2 | 3 | 6 | P1 | ingest P-H1/P-H8; rejection non-effects | AD-1, AD-8 | API |
| R-13 | External mocked workload/reservation facts become owned mutable truth | 1 | 3 | 3 | P2 | I-H6/I-M5 | AD-8 | Architecture + contract |
| R-14 | Adapter wall clock or hard sleeps make boundary tests nondeterministic | 2 | 2 | 4 | P2 | Time clauses; Clock port | AD-2 | Unit + static check |
| R-15 | Invalid DTO/schema values drift across Python/OpenAPI/events | 2 | 2 | 4 | P2 | typed error catalog and schemas | AD-1, AD-8 | Schema + API |
| R-16 | Queue/retention behavior is presented as production capacity without evidence | 1 | 2 | 2 | P3 | NFR-12 non-claims | AD-1 | NFR review |

## Test-level allocation

| Level | Planned share | Purpose |
|---|---:|---|
| Unit / pure domain | 55% | Reducer precedence, strict boundaries, policies, property-based vectors |
| Contract / integration | 25% | idempotency, CAS, atomic UoW, SQL constraints, emitted events |
| API | 15% | DTO validation, typed errors/status, request/response field agreement |
| E2E | 5% | canonical simulated fleet and four mandatory journeys through local adapters |

Pure domain logic has the highest allocation. E2E remains small and simulated; no physical GPU, DCGM, Prometheus, Kubernetes, scheduler, or adjacent module is required.

## Coverage gates

- 100% of P0 contracts have at least one executable RED test.
- Domain line coverage target is at least 90% once implementation begins; Phase 3 records no fabricated coverage.
- Every AD-1 through AD-8 has a RED test that would fail if its rule were removed.
- Every typed rejection test asserts zero projection/history/audit/event/lock side effects as applicable.
- No test uses real sleep or wall time; all time moves through `fake_clock`.

## Test IDs and allocation

`HB-*` covers heartbeat/thermal/reboot/silence; `ST-*` covers reducer/flapping/explainability; `MT-*` covers maintenance; `SC-*` covers schema/isolation. P0 coverage is `ST-FLAP-001`, `HB-ORDER-001`, `HB-IDEM-001`, and `MT-CONC-001`.

## TEA skill matrix

| Workflow | BMad TEA Skill | Artifact Produced | Defect Caught in This Package |
|---|---|---|---|
| Risk-Based Test Strategy | `bmad-testarch-test-design` | `test/test-design.md` | Prevented equal priority inflation and exposed four P0 mutation risks |
| Framework Initialization | `bmad-testarch-framework` | `test/fixtures/`, `test/conftest.py` | Prevented wall-clock sleeps and physical dependency leakage |
| ATDD Test Generation | `bmad-testarch-atdd` | `test/atdd/gpu_lab_digital_twin_contracts_test.py` | Exposed unimplemented contract ports through real RED failures |
| CI Quality Gate | `bmad-testarch-ci` | `test/ci/quality-gate.yml` | Prevented fake PASS behavior and checks RED reason explicitly |
| NFR Evidence | `bmad-testarch-nfr` | `test/nfr-evidence.md` | Prevented runtime claims before implementation evidence exists |
| Test Quality Review | `bmad-testarch-test-review` | `reviews/review-test-quality.md` | Caught weak non-effect/concurrency/explanation assertions |
| Traceability Matrix | `bmad-testarch-trace` | `test/traceability-matrix.md` | Prevented orphan ADs, P0 risks, requirements, and stories |

## Entry and exit

Entry: Phase 0–2 closed; contracts/schemas exist; no blocking design finding. Exit: tests collect and fail only at `NotImplementedError` from named operation stubs; all P0/AD links exist; review has no blocker. Turning tests green belongs to a later implementation phase.
