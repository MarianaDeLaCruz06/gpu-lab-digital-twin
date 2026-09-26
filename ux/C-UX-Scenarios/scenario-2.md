---
title: Scenario 2 — Thermal Anomaly and Automatic Cordon
status: final
created: 2026-09-26
---

# Scenario 2: Carlos contains ws-gpu-14 thermal risk

## Protagonist

**Carlos — Hardware Lab Technician**, monitoring the fleet during active lab use. He needs immediate proof that unsafe hardware is excluded from new work without implying that this module terminated existing work.

## Trigger

Fault Injector submits a valid simulated heartbeat for `ws-gpu-14` where one GPU reports a temperature strictly greater than 88°C.

## Preconditions

- `ws-gpu-14` exists in the canonical inventory and has a current accepted heartbeat.
- Carlos has previewed the simulated thermal payload and confirmed its target.
- No maintenance state has higher display precedence; if it does, thermal remains a retained secondary reason.

## Primary path

1. Carlos opens Fault Injector, selects the Thermal anomaly preset and `ws-gpu-14`, and enters/previews a value above 88°C.
2. Confirmation states that the input is simulated, that the state machine chooses the result, and that a qualifying thermal result cordons the entire node from new work.
3. On Apply, the event passes through normal heartbeat validation; the UI does not mutate the card directly.
4. Fleet Dashboard opens/updates one Critical alert episode for `ERR_THERMAL_88` and updates `ws-gpu-14` in place.
5. The card shows `DEGRADED` and separate `CORDONED`, the exact temperature and GPU ID, last accepted time, and “Why?” link.
6. Carlos opens Node Detail and reads the explanation, current telemetry context, prior/result state, threshold comparison, rule ID, and evidence/version.

## Failure path

- A value equal to 88°C does not trigger the thermal rule; preview explicitly states the strict `>88°C` boundary.
- A non-finite, missing, or capacity-invalid payload is rejected, preserves last-known-good data, and identifies the invalid field.
- If a maintenance lock is active, the primary state remains `DRAINING` or `MAINTENANCE`; the thermal reason and cordon remain visible and block unsafe release.
- Thermal recovery is not guessed. ODD-4 remains visible until the state machine reports an approved clear decision.

## System feedback

- One assertive screen-reader announcement for the newly opened critical thermal episode; subsequent observations update silently/politely.
- Durable alert row shows node, severity, `ERR_THERMAL_88`, opened/last-observed times, and update count.
- Explainability banner: “Cordoned: GPU 0 reported [value]°C, above the >88°C rule,” with cited evidence.
- Applied simulation confirmation links to Node Detail and never says the hardware was physically changed.

## Surfaces involved

- Fault Injector — preview, confirmation, and application result.
- Fleet Dashboard — stable card update and critical alert rail.
- Node Detail — telemetry, reasons, timeline, and external/mock context.

## State transitions

- Normal unlocked current node: `HEALTHY → DEGRADED`, `cordoned=false → true`.
- Higher-precedence maintenance: state remains `DRAINING`/`MAINTENANCE`; `THERMAL_OVER_88` is retained and cordon remains true.
- Exit from `DEGRADED`: only when every active reason's approved clear rule is satisfied; ODD-4 is not invented by UX.

## Success condition

Carlos sees `ws-gpu-14` cordoned with `DEGRADED`, can identify the GPU and exact temperature that crossed the strict threshold, and can distinguish containment from workload termination.

## Traceability

- **FRs:** FR-2, FR-5, FR-7, FR-11, FR-12, FR-13.
- **NFRs:** NFR-3, NFR-6, NFR-7, NFR-9, NFR-10, NFR-13.

