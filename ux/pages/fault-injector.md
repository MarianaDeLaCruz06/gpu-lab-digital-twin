---
title: Fault Injector — UX Specification
status: final
created: 2026-09-26
related_scenarios: [S-1, S-2, S-3]
---

# Fault Injector

## Purpose and protagonist

Controlled simulator surface for **Carlos** to generate reproducible telemetry and connectivity inputs. It exercises the same validation/state-evaluation path as normal simulated ingestion and never mutates twin state directly.

## Layout

Desktop split view: preset/target form left; immutable event preview and expected evaluation route right; recent simulated event results below. Narrow screens stack in that order. It is visually distinct from Node Detail to prevent simulation controls from appearing as physical hardware controls.

## Components

| ID | Component | Behavior |
|---|---|---|
| FI-01 | Simulation banner | Persistent `SIMULATION ONLY · no physical GPU action` |
| FI-02 | Preset selector | Normal heartbeat, pause/silence, thermal anomaly, reboot/state loss, maintenance workload snapshot, five-second connectivity alternation |
| FI-03 | Target selector | Exactly one configured node; compatible defaults do not auto-apply |
| FI-04 | Parameter form | Preset-specific fields with units and boundary help |
| FI-05 | Event preview | Exact generated input, target, provenance, target evaluation/version, and route through FR-2/FR-7 |
| FI-06 | Expected-effects notice | Possible rule path, explicitly not a promise of final state |
| FI-07 | Confirm dialog | Verb + target + simulated effect; Confirm/Cancel |
| FI-08 | Result panel | Applied/rejected status, event/version ID, resulting state/cordon, rule, Node Detail link |

## Telemetry displayed

Target's current state/cordon and last accepted heartbeat; generated node ID, times, boot/session marker, GPU values, driver/storage values, external/mock refs when included, connectivity observation sequence, and event version after submission.

## State variants

- **Thermal preset:** help states `>88°C` triggers; 88°C does not.
- **Reboot preset:** displays old and proposed new boot/session IDs or state-loss marker.
- **Silence preset:** displays symbolic configured interval and clock advance; no default interval duration.
- **Flapping preset:** fixed authoritative observation cadence is every five seconds; stabilization and repeat-alert thresholds remain `OPEN DESIGN DECISION` (ODD-5/ODD-6).
- **Maintenance workload preset:** values are external/mock snapshots and cannot issue scheduler commands.

## Buttons and actions

- `Preview event` validates locally and displays immutable preview; no state change.
- `Apply simulated event to [node]` opens confirmation and then submits once.
- `Cancel` closes confirmation with no event.
- `View node result` opens Node Detail focused on generated evidence.
- No bulk fault application in Phase 2; the mandatory fleet stream preset may start periodic heartbeats for canonical fixture but does not combine fault mutations invisibly.

## Validation behavior

- Target must be one of 32 configured node IDs.
- Required fields, finite numeric values, recognized enums, VRAM capacity, storage capacity, temperature units, and per-node GPU count follow FR-2.
- Thermal preview states strict boundary before confirmation.
- New boot/session ID must differ for reboot preset.
- Flapping sequence preview lists observations; it does not invent the stabilization result timing.
- Duplicate submission is prevented while pending; repeat requires a new confirmation.
- If the target evaluation/version or compatible inventory changes between Preview and Confirm, cancel submission, announce `Preview out of date`, and require a new preview.

## Loading, empty, error, and success

- **Loading:** form is disabled while inventory/preset definitions load; simulation banner remains visible.
- **Empty:** if no configured nodes, show inventory error and link to Fleet Dashboard; never offer free-text unknown target.
- **Error:** field-level validation; server rejection includes code and preserves form for correction. A preview invalidated by target change is visibly expired and cannot be submitted.
- **Success:** result names target and event/version, distinguishes accepted input from resulting state, and links to evidence.

## Alerts

Fault Injector does not create its own alert semantics. Accepted events may cause the state engine to open/update Fleet Dashboard episodes; the result panel references them. Rejected input produces one inline error, not an operational alert.

## Accessibility

- Presets are a labeled radio group; fields expose units and constraints.
- Preview uses a structured definition list/table, not raw color-coded JSON only.
- Confirmation focus is trapped and returns to Apply/first invalid field.
- Result is announced politely; resulting critical thermal episode is announced once by global alert behavior.
- Simulation status is visible text, not icon/color alone.

## Traceability

FR-2, FR-3, FR-5, FR-6, FR-10, FR-12, FR-13; NFR-2–10, NFR-13.
