---
title: 'Story 3.4 - Contain intermittent connectivity flapping'
type: 'feature'
created: '2026-11-07'
status: 'in-review'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '3abc6f2dc4001a8bb3d72d3fd70ad7eb1d504017'
context: ['{project-root}/docs/epic-2-context.md', '{project-root}/planning/ARCHITECTURE.md', '{project-root}/docs/contracts/behavioral-contracts.md']
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** Five-second ONLINE/OFFLINE connectivity evidence must not cause public node-card oscillation or alert flooding. The Impl-2 Annex proposes `>3` transitions in 60 seconds and `FLAPPING_CORDONED`, but canonical AD-5 leaves ODD-5 strategy and numeric enter/clear thresholds unresolved.

**Approach:** Implement the canonical unresolved-policy containment for task Story 3.4 (canonical backlog Story 2.3): atomically retain every raw observation as evidence, hold the node's public state/connectivity/cordon tuple, and upsert one current `ERR_POLICY_UNRESOLVED` diagnostic. Do not activate flapping, invent thresholds, or create a new state.

## Boundaries & Constraints

**Always:** Preserve AD-1 atomicity, AD-4 reducer ownership, and AD-5 evidence-only behavior; use the injected `Clock`/`FakeClock`; serialize evaluation with the existing write lock; make duplicate event IDs idempotent; keep the public node revision and eligibility unchanged; reuse the partial unique open-reason persistence model.

**Never:** Add `FLAPPING_CORDONED`; interpret Annex pulses as heartbeat loss/recovery; add a duplicate endpoint; emit `ERR_CONNECTIVITY_FLAPPING` before ODD-5 approval; use sleeps, wall time, hardware, or a second alert architecture; implement Stories 3.5 or 3.6.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Canonical pulse sequence | HEALTHY eligible node; 12 alternating observations at 5-second FakeClock intervals | Each observation is recorded; public tuple/revision remains stable; one open `ERR_POLICY_UNRESOLVED` diagnostic; zero flapping alerts | N/A |
| Annex boundary | Exactly 3 and then 4 transitions inside 60 seconds | Both are evidence-only holds because ODD-5 has no approved threshold | Explanation names ODD-5 rather than claiming quarantine |
| Duplicate evidence | Same event ID and payload replayed | `DUPLICATE`; no second audit record and no diagnostic update | Changed payload for the same ID is `ERR_IDEMPOTENCY_CONFLICT` |
| Invalid ordering | Naive/future/out-of-order observation instant | No mutation | Typed clock/schema rejection |

</frozen-after-approval>

## Code Map

- `src/gpu_lab_twin/domain/connectivity_policy.py` -- pure AD-5 unresolved policy; no framework or clock access.
- `src/gpu_lab_twin/application/connectivity_service.py` -- Clock-driven orchestration under the shared write lock.
- `src/gpu_lab_twin/ports/inbound/connectivity.py` -- observation/result contract used without adding an HTTP route.
- `src/gpu_lab_twin/ports/outbound/node_repository.py` -- atomic evidence/diagnostic commit model.
- `src/gpu_lab_twin/adapters/db/node_repository.py` -- transaction, event-id idempotency, and existing partial-unique diagnostic upsert.
- `src/gpu_lab_twin/bootstrap.py` -- wire the new service to the existing repository, clock, and lock.
- `tests/acceptance/test_story_3_4_connectivity_flapping.py` -- Flow A executable acceptance boundaries and stability proof.
- `tests/unit/test_connectivity_policy.py` -- post-RED policy vectors if needed during Green/Refactor.

## Tasks & Acceptance

**Execution:**
- [x] Create acceptance tests and execute authentic RED before production changes.
- [x] Add pure unresolved connectivity policy and value objects.
- [x] Add atomic repository commit reusing audit events plus the single-open-reason index.
- [x] Wire the service without adding or changing public endpoints.
- [x] Verify targeted tests, full suite, lint, formatting, sleeps, and evidence.

**Acceptance Criteria:**
- **AC-1:** Given a HEALTHY eligible node, when canonical five-second ONLINE/OFFLINE observations are submitted using FakeClock, then state, connectivity, cordon, eligibility, and revision remain equal to their stable baseline.
- **AC-2:** Given exactly three transitions and then a fourth within 60 seconds, when ODD-5 remains unresolved, then neither boundary activates flapping or invents a threshold; each result explains `ERR_POLICY_UNRESOLVED` and ODD-5.
- **AC-3:** Given repeated pulses, when evidence is committed, then exactly one open unresolved diagnostic exists, no `ERR_CONNECTIVITY_FLAPPING` alert exists, and every unique observation has one audit record.
- **AC-4:** Given a duplicate event, when replayed, then it returns `DUPLICATE` without duplicate audit/diagnostic effects; a conflicting reuse is rejected atomically.

## Implementation Notes

Task numbering is retained as 3.4 for the Impl-2 Annex; the canonical Plan-2/Solu-2 story is Epic 2 Story 2.3. Initial human approval is the explicit instruction to proceed while preserving binding existing contracts and recording Annex adaptations.

Implementation added the pure `evaluate_connectivity` hold policy, a Clock-driven serialized service, an inbound port/result, and an atomic repository method. Raw evidence is stored as `ConnectivityObserved` audit events; the existing open-reason index deduplicates the administrative unresolved diagnostic. No schema migration or HTTP route was added. Targeted Green reached 7/7 including a simultaneous duplicate test.

## Spec Change Log

## Review Triage Log

The build workflow's independent subagent review layers were unavailable under the active no-delegation policy. A direct diff audit found and patched one verification gap before final validation: the matrix promised naive/future/out-of-order time rejection, but the first Green implementation only rejected naive/future input. The service now rejects evidence earlier than the last accepted connectivity observation, and an atomic zero-effect test covers all three cases. No unresolved review findings remain.

## Design Notes

The `alerts` table is reused as the approved single-open-reason persistence model for the administrative diagnostic. A row with reason `ERR_POLICY_UNRESOLVED` is diagnostic state, not an `ERR_CONNECTIVITY_FLAPPING` incident. Raw observations are immutable `ConnectivityObserved` audit events. This avoids a new table/migration and a competing alert mechanism while satisfying I-T4/I-T5.

## Verification

**Commands:**
- `uv run pytest tests/acceptance/test_story_3_4_connectivity_flapping.py -q` -- all Story 3.4 acceptance tests pass after the recorded RED.
- `uv run pytest -ra` -- all tests pass with zero skipped.
- `uv run ruff check .` and `uv run ruff format --check .` -- clean.
- `rg -n "time\\.sleep|waitForTimeout|sleep\\(5000" src tests` -- no hardcoded sleeps.
