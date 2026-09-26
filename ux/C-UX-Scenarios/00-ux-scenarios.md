---
title: GPU Lab Digital Twin — UX Scenario Index
status: final
created: 2026-09-26
updated: 2026-09-26
sources:
  - ../../planning/prd.md
  - ../EXPERIENCE.md
---

# UX Scenario Index

These four scenarios cover the authoritative Module 3 journeys. All use the desktop-first Fleet Dashboard, simulated inputs, deterministic PRD state vocabulary, separate cordon eligibility, and causal explanations. Reservations and workloads are external/mock read-only context.

| ID | Scenario | Primary protagonist | Trigger | Primary surfaces | State path | PRD trace |
|---|---|---|---|---|---|---|
| S-1 | Fleet Heartbeat Ingestion | Carlos | Periodic simulated heartbeats and clock evaluation | Fleet Dashboard, Node Detail | `UNKNOWN → HEALTHY`; current state `→ OFFLINE` only after `>3` intervals | FR-1–4, FR-7, FR-11–13; NFR-1, 4–7, 9–10 |
| S-2 | Thermal Anomaly & Automatic Cordon | Carlos | `ws-gpu-14` GPU temperature `>88°C` | Fleet Dashboard, Node Detail, Fault Injector | `HEALTHY → DEGRADED`; `cordoned=false → true` | FR-2, FR-5, FR-7, FR-11–13; NFR-3, 6–7, 9–10, 13 |
| S-3 | Simulated Workstation Reboot | Alex | `ws-gpu-05` boot/session change or state-loss marker | Fleet Dashboard, Node Detail, Fault Injector | current unlocked state `→ RECOVERING`; later result only from state machine | FR-3, FR-6–7, FR-11–13; NFR-5–7, 9–10, 13 |
| S-4 | Maintenance Drain | Carlos | Maintenance lock on dual-GPU server | Node Detail, Maintenance Control, Fleet Dashboard | `HEALTHY → DRAINING → MAINTENANCE`; release reevaluates | FR-7–9, FR-11–13; NFR-2, 6–7, 10, 13 |

## Surface coverage

| Surface | S-1 | S-2 | S-3 | S-4 |
|---|---:|---:|---:|---:|
| Fleet Dashboard | ✓ | ✓ | ✓ | ✓ |
| Node Detail | ✓ | ✓ | ✓ | ✓ |
| Fault Injector | Supporting | ✓ | ✓ | Supporting |
| Maintenance Control | — | — | — | ✓ |

## State and feedback coverage

| Required UX condition | Covered in |
|---|---|
| Loading / empty / error / success | All page specs and `EXPERIENCE.md` |
| Heartbeat freshness and silent-node explanation | S-1 |
| Thermal alert, `DEGRADED`, and separate `CORDONED` | S-2 |
| State-loss evidence and `RECOVERING` | S-3 |
| Active workload visibility and graceful drain | S-4 |
| Five-second online/offline flapping without visual oscillation or alert flooding | S-1 failure path and mandatory edge-case contract below |

## Mandatory edge-case contract

A node alternates simulated `ONLINE`/`OFFLINE` observations every five seconds. The Fleet Dashboard keeps the last stable public state in its primary position, shows `CONNECTIVITY UNSTABLE` and `CORDONED`, and updates one open `(node_id, ERR_CONNECTIVITY_FLAPPING)` alert episode. Raw observations remain visible on Node Detail. The UI does not flash, reorder, swap state one-for-one, create repeated toasts, or invent a countdown.

**OPEN DESIGN DECISION:** ODD-5 stabilization/clear criteria and ODD-6 repeat-alert timing remain unresolved. Phase 2 defines their presentation but does not choose numeric values.

## Quality gate

- Four of four authoritative scenarios have named protagonists, triggers, preconditions, primary and failure paths, feedback, surfaces, state transitions, success conditions, and PRD traceability.
- Carlos owns operational containment and maintenance journeys; Alex receives comprehensible availability/recovery evidence without scheduler controls.
- Every automated change has a reason, rule ID, evidence/version, and timestamp.
- No scenario creates reservations, schedules jobs, kills workloads, or uses physical GPU hardware.

