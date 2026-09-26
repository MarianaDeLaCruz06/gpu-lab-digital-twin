# Adversarial Review — Module 3 GPU Lab Digital Twin PRD

Date: 2026-09-26  
Artifact reviewed: `planning/prd.md` (initial Phase 1 draft)  
Lens: BMad `adversarial`  
Artifact class: Behavioral requirements document

## Review verdict

The draft is strongly scoped, test-oriented, and covers all mandatory scenarios, but the initial version left several fail-closed and data-contract details implicit. Twelve adversarial findings were identified. Eight are accepted and applied to the PRD, two are deferred as explicit non-blocking design decisions for implementation readiness, and two are rejected because their proposed changes would either contradict the authoritative source or expand Module 3 into another module.

## Findings and triage

### ADV-01 — Unknown driver status lacks an explicit fail-closed result

- **Location:** §7.2 ODD-8; §11 state model; §13 error model
- **Trigger condition:** A heartbeat supplies a syntactically recognized driver status whose health mapping has not yet been configured.
- **Guard snippet:** Require `ERR_POLICY_UNRESOLVED`, retain/enter a cordoned safe state, and forbid `HEALTHY` until the mapping is approved.
- **Potential consequence:** A driver condition could be treated as healthy merely because the vocabulary is unresolved.
- **Triage:** **ACCEPT** — Fail-closed behavior is necessary and remains within twin ownership.
- **Applied change:** Clarified ODD-8, FR-7, the state model, and the error model so unresolved driver interpretation cannot yield `HEALTHY`.

### ADV-02 — Degradation clearing is underspecified beyond thermal release

- **Location:** §7.2 ODD-4/ODD-8; §11.4 `DEGRADED` exit
- **Trigger condition:** Thermal, driver, and flapping reasons clear at different times or one clear rule is absent.
- **Guard snippet:** State that each reason has an independent clear rule; all active reasons must clear; an absent clear rule holds the node cordoned under `ERR_POLICY_UNRESOLVED`.
- **Potential consequence:** One recovered metric could incorrectly clear another active safety condition.
- **Triage:** **ACCEPT** — The state-machine exit guard must be conjunctive and fail closed.
- **Applied change:** Added independent reason-lifecycle and conjunctive clear rules.

### ADV-03 — Conflicting maintenance sources are ambiguous

- **Location:** §12 `maintenance_lock_observed`; FR-8/FR-9
- **Trigger condition:** Carlos's command record says locked while a heartbeat says unlocked, or vice versa.
- **Guard snippet:** Define Carlos's Module 3 command record as authoritative, treat heartbeat lock data as an observation only, and surface mismatch without auto-clearing the lock.
- **Potential consequence:** A stale heartbeat could prematurely release a maintenance cordon.
- **Triage:** **ACCEPT** — Safe authority precedence must be explicit.
- **Applied change:** Added mismatch behavior and a specific error code.

### ADV-04 — Official storage topology is not represented in the canonical inventory

- **Location:** FR-1; §12 telemetry model
- **Trigger condition:** Storage-free telemetry is validated without canonical capacity for workstation and server classes.
- **Guard snippet:** Include the official 500 GB NVMe workstation capacity and 4 TB NVMe server capacity in the canonical fixture while keeping the hardware simulated.
- **Potential consequence:** Storage values cannot be deterministically range-validated against the authoritative fleet profile.
- **Triage:** **ACCEPT** — These values come from `Task plan 2.pdf`, not invention.
- **Applied change:** Added simulated storage capacities to FR-1 and its acceptance condition.

### ADV-05 — The five-second connectivity input is not a first-class event

- **Location:** FR-10; FR-12; §12 telemetry model
- **Trigger condition:** The fault generator alternates online/offline independently of normal heartbeat silence calculations.
- **Guard snippet:** Define a simulated connectivity observation/fault-control event with node ID, observed status, and time; route it through state evaluation and preserve it separately from accepted telemetry.
- **Potential consequence:** Implementers may mutate state directly from the UI or incorrectly redefine heartbeat silence to manufacture flapping.
- **Triage:** **ACCEPT** — The mandatory edge case needs an explicit input contract.
- **Applied change:** Added `ConnectivityObservation` and prohibited direct state mutation.

### ADV-06 — Alert deduplication identity and closure are incomplete

- **Location:** FR-10; §10 domain entities; §13 error model
- **Trigger condition:** Repeated equivalent alerts arrive, reasons overlap, or a condition clears and later recurs.
- **Guard snippet:** Key an open episode by `(node_id, reason_code)`; update while open; close only on that reason's approved clear rule; a later recurrence creates a new episode.
- **Potential consequence:** Equivalent alerts may fan out, or distinct incidents may be merged forever.
- **Triage:** **ACCEPT** — This directly addresses the assignment's alert-flooding condition.
- **Applied change:** Added episode identity and lifecycle invariants.

### ADV-07 — Explanation evidence can drift from the actual evaluation trace

- **Location:** FR-13; NFR-7; §14
- **Trigger condition:** An explanation cites plausible current telemetry rather than the exact version and fields used by the state evaluation.
- **Guard snippet:** Bind every explanation to immutable evidence/version identifiers from the evaluation trace and test set equality between cited and evaluated evidence.
- **Potential consequence:** Carlos receives an explanation that cannot reproduce the decision.
- **Triage:** **ACCEPT** — Reproducible explanations are required by the official explainability constraint.
- **Applied change:** Strengthened FR-13 and NFR-7 with evidence/version binding.

### ADV-08 — Simultaneous fault precedence is specified but not directly tested

- **Location:** FR-7; §11.3; §15 traceability
- **Trigger condition:** Maintenance, silence, reboot, and thermal evidence coexist on one node.
- **Guard snippet:** Add pairwise and all-at-once precedence vectors that assert state, cordon, retained reasons, and release reevaluation.
- **Potential consequence:** Implementations may follow the table for isolated events yet contradict it under combined faults.
- **Triage:** **ACCEPT** — Determinism requires collision tests, not only prose.
- **Applied change:** Added explicit state-precedence NFR coverage.

### ADV-09 — An absolute ingestion/decision latency is unresolved

- **Location:** NFR-11; ODD-1/ODD-2
- **Trigger condition:** Reviewers expect a fixed millisecond limit before heartbeat cadence and local runtime constraints are selected.
- **Guard snippet:** Approve a numeric latency budget and sample size before implementation readiness, then bind the percentile test to them.
- **Potential consequence:** Performance cannot receive a final readiness sign-off yet.
- **Triage:** **DEFER** — The source gives no latency value, and inventing one is expressly prohibited. NFR-11 retains numeric percentile coverage and marks the missing numeric budget as an open design decision. This is non-blocking for Phase 1 but blocking for implementation readiness.

### ADV-10 — Telemetry/decision history retention has no duration or capacity

- **Location:** NFR-12; ODD-2
- **Trigger condition:** An implementer chooses unlimited history or silently truncates audit evidence.
- **Guard snippet:** Approve numeric duration and record-capacity limits before implementation readiness.
- **Potential consequence:** Storage and audit behavior remain unbounded.
- **Triage:** **DEFER** — The sources provide no retention value. Selecting one in this PRD would violate the human instruction. The open decision is explicit and non-blocking for Phase 1.

### ADV-11 — Reboot detection relies on a simulated boot/session identifier

- **Location:** §7.1; FR-6; §12
- **Trigger condition:** A reviewer treats the boot/session field as an unsupported implementation assumption and proposes removal.
- **Guard snippet:** Replace it with heuristic state-loss inference from missing telemetry.
- **Potential consequence:** Removal would make reboot detection ambiguous and non-deterministic.
- **Triage:** **REJECT** — The authoritative scenario requires state-loss detection, while the prototype is explicitly simulated. A boot/session ID or explicit state-loss marker is a disclosed, hardware-agnostic test fixture assumption, not institutional context. Heuristic timing would require another invented threshold.

### ADV-12 — Carlos command authorization is not specified

- **Location:** FR-8/FR-9; Module boundaries
- **Trigger condition:** An unauthenticated actor invokes the prototype maintenance control.
- **Guard snippet:** Add identity, RBAC, and authorization enforcement to Module 3.
- **Potential consequence:** A production deployment could expose maintenance actions too broadly.
- **Triage:** **REJECT** — Identity/role enforcement belongs outside Module 3, and adding it would leak into another subsystem. The standalone prototype uses a named Carlos fixture and must label authorization as external rather than claim to enforce it.

## Required-check coverage

| Check | Result |
|---|---|
| Scope leakage into Modules 4, 6, 9, or 11 | No leakage after triage; read-only mocked boundaries are explicit |
| Vague requirements | No unquantified elastic terms found in FR acceptance conditions; ODDs are explicit |
| Missing numeric NFR criteria | Two source-unspecified numeric policies remain explicit ODDs; no value was invented |
| Scenario-to-FR traceability | All 4 mandatory scenarios plus the edge case are traced |
| Carlos/Alex journey coverage | Both named protagonists have journey and scenario coverage |
| State-transition contradictions | Collision-test gap accepted and fixed; precedence is deterministic |
| Silent-node behavior | Strict `>3 intervals` boundary, stale-event protection, cordon, and explanation defined |
| Unsafe thermal handling | Strict `>88°C`, whole-node cordon, independent clear policy, fail-closed release defined |
| Flapping state oscillation | Public transitions are stabilized; direct mutation prohibited |
| Alert flooding | One open episode per `(node_id, reason_code)` with explicit lifecycle |
| Untestable statements | ODD-dependent statements identify the decision needed before readiness |
| Unsupported assumptions | Boot/session fixture assumption disclosed and retained with rationale |

## Finding counts

- **Total:** 12
- **Accepted:** 8
- **Deferred:** 2
- **Rejected:** 2
- **Blocking findings remaining for Phase 1:** 0
- **Items that must be resolved before implementation readiness:** ODD-1 through ODD-8 as identified by their closure conditions, including ADV-09 and ADV-10

