---
title: 'Story 3.6 Maintenance Drain Orchestration and Interactive Fleet Map E2E'
type: 'feature'
created: '2026-11-07'
status: 'in-progress'
route: 'dispatch'
review_loop_iteration: 0
context: ['planning/ARCHITECTURE.md', 'planning/detailed-design/contracts.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Carlos needs to drain the dual-GPU server from a 32-node fleet view and see an honest, deterministic transition from eligible to draining to maintenance.

**Approach:** Implement the existing AD-7 maintenance contract using `maintenance_locks`, the injected Clock, repository atomicity, `DRAINING` and `MAINTENANCE`; expose the canonical maintenance-drain route and workload fixture route, then drive them through a minimal server-hosted fleet UI and Playwright Page Object.

## Boundaries & Constraints

**Always:** Keep `central-gpu-server` as the domain ID; show the Annex alias `server-gpu-01` only as a UI label. Lock acquisition immediately cordons. Only a fresh post-lock `EXTERNAL_MOCK` workload snapshot with zero count reaches `MAINTENANCE`. Identical requests replay idempotently.

**Never:** Invent states, duplicate maintenance persistence, terminate jobs, add fixed waits, mock the browser page/backend, or bypass typed errors and repository boundaries.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Schedule | Healthy eligible server, expected revision | One active lock, `DRAINING`, cordoned | Revision/active-lock conflict is typed 409 |
| Replay | Same request ID and payload | Original result, no duplicate lock | Changed payload is `ERR_IDEMPOTENCY_CONFLICT` |
| Completion | Newer post-lock zero-workload snapshot | `MAINTENANCE`, cordoned | Stale/pre-lock snapshot cannot complete |

</frozen-after-approval>

## Code Map

- `src/gpu_lab_twin/domain/maintenance.py` -- immutable command/snapshot policy and hashes.
- `src/gpu_lab_twin/application/maintenance_service.py` -- serialized orchestration.
- `src/gpu_lab_twin/adapters/db/node_repository.py` -- atomic lock, projection, audit/history updates.
- `src/gpu_lab_twin/api/routes/maintenance.py` -- canonical HTTP adapters.
- `src/gpu_lab_twin/api/static/fleet-map.*` -- minimal interactive 32-node fleet surface.
- `tests/e2e/pages/FleetMapPage.ts` -- all selectors and workflow actions.

## Tasks & Acceptance

**Execution:**
- [ ] Implement maintenance policy, port, service, atomic repository operations, DTOs and routes.
- [ ] Add the fleet UI and deterministic simulated workload completion action.
- [ ] Add Playwright configuration, POM, and success/replay/error/integrity tests.
- [ ] Capture authentic run output and trace configuration/artifact location.

**Acceptance Criteria:**
- Given an eligible server, when Carlos schedules maintenance, then the UI shows draining and the backend has exactly one active lock and `cordoned=true`.
- Given a fresh simulated zero-workload snapshot, when the UI refreshes, then the node shows maintenance and remains unavailable for work.
- Given repeated or conflicting requests, then replay is idempotent and conflict is clearly rendered.
- Given the fleet page, then exactly 32 real API-backed cards are present.

## Implementation Notes

Architecture §9.7/§9.8 uses older illustrative `/api/...` paths; the binding OpenAPI paths under `/v1/...` remain authoritative.

## Spec Change Log

## Review Triage Log

## Verification

**Commands:**
- `uv run pytest tests/integration/test_story_3_6_maintenance.py` -- backend behavior passes.
- `npx playwright test` -- browser uses the real local service and all scenarios pass.

