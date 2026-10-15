# Solu-2 NFR Evidence Plan

No production implementation exists, so every status is `PLANNED`. This is an evidence plan, not runtime evidence. Measurements use simulated inputs, injected time, and isolated test databases only.

| NFR | Metric / Threshold | How Measured | Tool / Fixture | N / Concurrency | Evidence Artifact | Status |
|---|---|---|---|---|---|---|
| NFR-1 Fleet completeness | Exactly 32 unique nodes, 33 GPUs, 840 GB VRAM | Fixture cardinality and uniqueness assertions | `seed_fleet` + pytest | 1 canonical run | future `nfr-fleet.xml` | PLANNED |
| NFR-2 Hardware independence / security isolation | 0 physical GPU/CUDA/NVML and 0 adjacent-module calls | import/dependency scan plus mandatory suite in clean container | CI static scan, simulated adapters | Full suite, 1 isolated runner | future `dependency-scan.txt` | PLANNED |
| NFR-3 Thermal safety | 100% samples `>88°C` unconditionally ineligible before exposure; 88°C produces 0 thermal cordons | boundary/property cases and atomic projection assertions | hypothesis, `sim_telemetry`, DB harness | N=1,000 generated samples; 8 workers against distinct nodes | future `nfr-thermal.xml` | PLANNED |
| NFR-4 Silence boundary | 0 early OFFLINE at `3×`; 100% detection at `>3×` next evaluation | fake-clock boundary vectors | `fake_clock`, pytest | N=1,000 intervals, sequential per node | future `nfr-silence.xml` | PLANNED |
| NFR-5 Idempotency / reliability | 100 replays → 1 applied version, ≤1 matching transition/open alert | replay and concurrent duplicate tests | pytest-asyncio, DB harness | N=100 replays; concurrency 16 | future `nfr-idempotency.xml` | PLANNED |
| NFR-6 Determinism | 1 distinct output tuple across 1,000 repeats/vector | hash normalized reducer outputs | hypothesis + fake clock | N=1,000/vector; no shared node concurrency | future `nfr-determinism.json` | PLANNED |
| NFR-7 Explainability | 100% transitions/cordons/holds/rejections contain required structured evidence | assertion helper over all mandatory vectors | `explain_assert` | All generated decisions | future `nfr-explainability.xml` | PLANNED |
| NFR-8 Flapping containment | 12 five-second observations → 0 one-for-one public transitions, 0 flapping alerts and exactly 1 unresolved diagnostic while ODD-5 open | compare all externally visible tuples and episode counts | `fake_clock`, `sim_telemetry` | N=12, one serialized node stream | future `nfr-flapping.xml` | PLANNED |
| NFR-9 Data integrity / isolation | 0 malformed, unknown, duplicate, or late inputs overwrite last-known-good telemetry | before/after projection and cross-node snapshot assertions | API tests + DB harness | N=1,000 invalid payloads; concurrency 8 | future `nfr-integrity.xml` | PLANNED |
| NFR-10 Prototype coverage | 4/4 mandatory scenarios and 1/1 edge case pass | named scenario report | pytest markers/JUnit | One complete suite | future `mandatory-scenarios.xml` | PLANNED |
| NFR-11 Decision exposure ordering / performance | 100% atomic exposure; record latency only, no SLA | drive one event per node concurrently, verify fleet version published only after all commits; record distribution | pytest-asyncio, FakeClock, PostgreSQL harness | 32 concurrent node events; N=30 batches | future `nfr-exposure-latency.json` | PLANNED |
| NFR-12 Process-local boundary / recovery | exactly 1 projection/node; restart resets 32 nodes; no durable-history claim | controlled harness restart and inventory reset assertions | seed fixture + test process | N=10 restarts, serial | future `nfr-restart.xml` | PLANNED |
| NFR-13 Precedence collision coverage | 10/10 rows, all condition pairs, one all-at-once vector | parameterized transition matrix | hypothesis/pytest | 10 rows + 15 pairs + 1 combined | future `nfr-precedence.xml` | PLANNED |

Performance evidence is limited to NFR-11 ordering plus baseline measurement at explicit concurrency 32. Reliability/recovery evidence is planned under NFR-5/NFR-12. Security/isolation evidence is planned under NFR-2/NFR-9. No numeric production latency or capacity claim is introduced.
