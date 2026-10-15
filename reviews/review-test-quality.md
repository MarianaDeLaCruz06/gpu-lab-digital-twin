# Phase 3 TEA Test Quality Review

Scope: `test/atdd/`. Test Lead: Julian Motta. Reviewer: Mariana De La Cruz. Dimensions: Determinism, Isolation, Assertions, Structure, Performance. The suite is intentionally RED only because three named contract stubs raise `NotImplementedError`.

| ID | Severity | Issue | Recommendation | Triage | Rationale | Owner | Applied Fix |
|---|---|---|---|---|---|---|---|
| TQ-01 | Critical | Time-based cases could accidentally use wall time or sleep. | Use one timezone-aware advanceable fake clock and scan for hard sleeps. | ACCEPT | Silence/flapping boundaries must be deterministic. | Julian | `fake_clock` fixture plus CI grep; zero sleeps. |
| TQ-02 | Critical | A skipped or expected-NotImplemented suite would be falsely green. | Call stubs directly and require failing `NotImplementedError`; CI verifies nonzero exit and exact reason. | ACCEPT | RED must be executable and honest. | Mariana | No skip/xfail; RED-reason gate added. |
| TQ-03 | High | Precondition tests can accidentally validate only an error code and miss mutation. | Snapshot all observable effects before rejection and compare afterward. | ACCEPT | Rejection non-effects are contract postconditions. | Julian | Unknown node, invalid transition/drain, and cross-node tests assert unchanged probes. |
| TQ-04 | High | Duplicate tests may test a mock's configured count rather than external effects. | Assert revision and independent history/audit/event/alert/lock counts. | ACCEPT | Avoids mock-self-testing. | Mariana | EffectProbe exposes independent effect collections; deep assertions added. |
| TQ-05 | Critical | Flapping check could assert only the final state while allowing 11 intermediate oscillations. | Capture every externally visible tuple and bound both flapping alerts and unresolved diagnostic episodes. | ACCEPT | P0 requires path depth, not endpoint-only checking. | Julian | `ST-FLAP-001` asserts the full 12-observation sequence. |
| TQ-06 | High | Explainability checks could be tautological (`value == value`). | Assert fixed observed values and exact threshold/operator or expected state. | ACCEPT | Ensures removed rule/threshold data fails. | Mariana | `explain_assert` plus thermal/silence/reboot/drain cases. |
| TQ-07 | High | Sequential duplicate drain test would miss a concurrent unique-index race. | Use `asyncio.gather` with the same request and assert one lock/event. | ACCEPT | AD-1/AD-7 explicitly cover simultaneous calls. | Julian | `MT-CONC-001` added. |
| TQ-08 | Medium | Tests may become slow if real database/hardware setup happens at import time. | Keep DB as an ephemeral harness plan and all hardware inputs simulated. | ACCEPT | Phase 3 contains scaffolding, not adapters. | Mariana | DB fixture validates migration path only; no network/process startup. |
| TQ-09 | Medium | Pure-domain coverage could be diluted by excessive E2E setup. | Keep domain tests the majority and E2E at 5%. | ACCEPT | Fast deterministic feedback supports reducer-heavy design. | Julian | Allocation documented in test design. |
| TQ-10 | Medium | Hypothesis is selected but not yet exercised in RED acceptance tests. | Add property suites during implementation when callable pure policies exist. | DEFER | Generating inputs around a stub adds no contract signal now. | Mariana | Recorded in NFR plan; no fake property evidence. |

Totals: ACCEPT 9 / DEFER 1 / REJECT 0. Blocking findings remaining: **0**.

## Review conclusion

- Determinism: fake time and deterministic UUID generation for scripted faults; no hard sleeps.
- Isolation: no physical dependencies; effect probes test cross-node and forbidden-command non-effects.
- Assertions: concrete boundaries, counts, state/cordon tuples, rule IDs, observed values, and thresholds.
- Structure: one RED seam, reusable fixtures, stable test IDs, and operation-focused cases.
- Performance: no real external startup in ATDD; planned concurrency is explicit and runtime claims remain PLANNED.
