---
title: Maintenance Control — UX Specification
status: final
created: 2026-09-26
related_scenarios: [S-4]
---

# Maintenance Control

## Purpose and protagonist

Operational surface for **Carlos** to set/release a Module 3 maintenance lock and observe graceful drain from external/mock workload snapshots. It is not a scheduler, workload controller, or authorization system.

## Layout

Desktop: node/lock summary header; requested-action panel left; current drain/maintenance evidence right; transition history below. Narrow tablet stacks panels. Below 768 px, monitoring remains but lock/release mutations are disabled with “Use a desktop viewport for maintenance changes.”

## Components

| ID | Component | Behavior |
|---|---|---|
| MC-01 | Node summary | Node ID/class/state/cordon, GPU topology, active reasons |
| MC-02 | Lock record | Carlos command status, reason, command time, heartbeat-observed status separately |
| MC-03 | Maintenance reason | Required text field for lock request; existing reason read-only while locked |
| MC-04 | Workload context | External/mock active count, IDs, provenance time; read-only |
| MC-05 | Drain progress | Count/list changes only; no percentage or ETA |
| MC-06 | Lock confirmation | Immediate cordon, expected `DRAINING`/`MAINTENANCE`, module limitations |
| MC-07 | Release confirmation | Warns that release reevaluates all health evidence and does not guarantee `HEALTHY` |
| MC-08 | Completion/result | Durable command and transition result with rule/evidence link |

## Telemetry displayed

Current node state, cordon, maintenance command record, observed heartbeat lock, active/retained reasons, latest accepted heartbeat, external/mock workloads and update time, and state transition evidence.

## State variants

| Variant | Treatment |
|---|---|
| Unlocked + workloads | Lock form; preview shows current workload count and immediate cordon consequence |
| `DRAINING` | Lock active, cordoned, remaining external/mock count/IDs, ODD-7 notice; no force action |
| `MAINTENANCE` | Lock active, cordoned, zero workloads, completion confirmation |
| Lock mismatch | Persistent `ERR_LOCK_SOURCE_MISMATCH`; command record remains authoritative |
| Already locked | Show existing command record and reason; do not replace it or submit a second lock command |
| Command outcome unknown | Disable lock/release retry; reconcile command record and timeline before offering another action |
| Coexisting health reasons | Retained under maintenance state and listed as release blockers/reevaluation inputs |
| Unresolved policy | `ERR_POLICY_UNRESOLVED`; safe state held; exact ODD named |

## Buttons and actions

- `Review maintenance lock` enabled when target exists and reason is non-empty.
- `Lock [node] for maintenance` in confirmation; one submission.
- `Review release` when locked.
- `Release maintenance lock` in confirmation; copy says reevaluation may select a non-healthy state.
- `Back to node detail` preserves context.
- Explicitly absent: terminate, checkpoint, reschedule, allocate, edit reservation, override health, force healthy.

## Validation behavior

- Target must be configured; maintenance reason must contain non-whitespace text.
- Duplicate command is disabled while pending.
- Preview binds target state, lock record, and workload snapshot versions. Any change before confirmation requires a refreshed preview.
- If the target is already locked, an identical request is shown as already satisfied and a conflicting reason is rejected; neither creates a second lock record.
- Active workload count cannot be edited and must be a non-negative external/mock value.
- Transition to `MAINTENANCE` occurs only from an accepted snapshot with count zero.
- Heartbeat lock observation never overrides the Carlos command record.

## Loading, empty, error, and success

- **Loading:** show identity and current lock shell; disable mutations until command/workload context resolves.
- **Empty:** no active workloads reads `0 external/mock active workloads`; missing snapshot is `— Not reported`, not zero.
- **Error:** command failure preserves reason and current state; stale workload source retains last-known list/time; mismatch has its own persistent banner. A transport failure without a definitive result shows `Outcome unknown`, prevents retry, and reconciles the authoritative record first.
- **Success:** lock success names resulting state and cordon; drain completion confirms zero reported workloads; release success names reevaluated result.

## Alerts

Drain blocked is one warning episode updated by snapshots. Lock mismatch is persistent until source agreement/explicit resolution. Thermal/silence/flapping alerts remain visible while maintenance has display precedence.

## Accessibility

- Confirmation dialog names action, node, immediate consequence, and limitations before the button.
- Workload count changes use a polite live region; individual repeated IDs are not re-announced.
- Error focus moves to reason or causal banner.
- Lock and observed-lock values are textually distinguished for screen readers.
- At narrow widths, disabled mutation has visible explanatory text and is not merely absent.

## Traceability

FR-7, FR-8, FR-9, FR-11, FR-13; NFR-2, NFR-6, NFR-7, NFR-10, NFR-13.
