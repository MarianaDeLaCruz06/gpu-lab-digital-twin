---
title: Node Detail — UX Specification
status: final
created: 2026-09-26
related_scenarios: [S-1, S-2, S-3, S-4]
---

# Node Detail

## Purpose and protagonist

Evidence-focused surface where **Carlos** diagnoses hardware/state and **Alex** understands availability. It binds the displayed decision to exact telemetry/observation versions and separates facts, external/mock context, and operational controls.

## Layout

Desktop: identity/state header; primary telemetry matrix; explainability panel; state timeline; right context rail for maintenance, reservation, and permitted controls. Below 1024 px, the context rail follows the timeline. Deep-link focus may open the relevant reason while retaining the whole page.

## Components

| ID | Component | Behavior |
|---|---|---|
| ND-01 | Identity header | Node ID, class, GPU topology, canonical state, connectivity, cordon, last evaluation |
| ND-02 | Explainability banner | Prior/result state, plain-language cause, rule, evidence/version IDs, event/evaluation times |
| ND-03 | GPU telemetry matrix | Per-GPU temperature and VRAM occupied/capacity; thermal threshold comparison |
| ND-04 | Node telemetry | Driver status, storage free/capacity, accepted heartbeat, boot/session evidence |
| ND-05 | Reason stack | Every active/retained reason with independent lifecycle and clear-policy status |
| ND-06 | State timeline | Immutable transitions, holds, alert episode updates, and rejected inputs |
| ND-07 | External/mock context | Read-only reservation refs and active workload refs/count with provenance timestamp |
| ND-08 | Maintenance context | Lock status, reason, command source, mismatch warning, link to Maintenance Control |
| ND-09 | Simulation action | Link to Fault Injector preselected for this node; Carlos fixture only |

## Telemetry displayed

Exact fields from PRD §12, including node/event/receive time, boot/session or state-loss marker, per-GPU metrics, driver health, storage, external/mock reservations/workloads, and observed maintenance lock. Every value displays provenance and freshness where ambiguity is possible.

## State variants

- **Thermal:** banner uses Critical treatment, identifies GPU and exact value; `DEGRADED` and `CORDONED` remain separate.
- **Silent/offline:** last accepted time, configured interval reference, elapsed count, strict `>3` comparison, and last-known values.
- **Recovering:** prior/new boot/session evidence and no percentage/ETA while ODD-3 is open.
- **Five-second alternation:** raw observation list, stable public state/connectivity/cordon, one current `ERR_POLICY_UNRESOLVED` diagnostic, and ODD-5/ODD-6 notice. `CONNECTIVITY UNSTABLE` and a single flapping episode appear only after an approved ODD-5 policy classifies the evidence.
- **Maintenance:** primary maintenance-related state plus retained health reasons; command record vs heartbeat observation shown separately.

## Buttons and actions

- `Back to fleet` preserves prior filters and focus.
- `Copy decision evidence` copies visible structured evidence and rule identifiers.
- `Open Fault Injector for [node]` navigates; it does not apply a fault.
- `Schedule maintenance` / `View maintenance` navigates to Maintenance Control for Carlos.
- Alex sees read-only context and no simulation or maintenance mutation control.
- No reservation edit, scheduling, kill, checkpoint, or physical hardware action.

## Validation behavior

- Unknown node route shows a not-found error and Back to fleet; it does not create a placeholder twin.
- Explanation evidence/version set must equal the state evaluation trace.
- Heartbeat lock mismatch cannot clear Carlos's command record.
- Old boot/session replay appears as ignored audit evidence and cannot overwrite current telemetry.

## Loading, empty, error, and success

- **Loading:** identity shell plus telemetry/timeline skeleton; node ID from route remains visible.
- **Empty:** no timeline after first heartbeat reads `No transitions recorded`; no external refs reads `None reported by external/mock source`.
- **Error:** preserve last-known detail, label stale, show Retry; evidence-copy error does not affect state.
- **Success:** requested node, current decision, and evidence versions agree; navigation confirmations link back here.

## Alerts

Active alert episodes appear at top of timeline and remain associated with their reason. Closed episodes show closure evidence. Only the first new critical thermal episode uses assertive announcement.

## Accessibility

- Heading includes node ID and current state; state/cordon are visible text with icon/color.
- Telemetry matrix uses semantic table headers and units in accessible names.
- Timeline uses an ordered list with prior/result state in each item.
- Copy confirmation uses a polite live region.
- Focus lands on the reason banner when opened from an alert, then follows page order.

## Traceability

FR-2–7, FR-9–11, FR-13; NFR-3–9, NFR-11–13.
