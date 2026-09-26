---
title: Scenario 1 — Fleet Heartbeat Ingestion
status: final
created: 2026-09-26
---

# Scenario 1: Carlos monitors fleet heartbeat ingestion

## Protagonist

**Carlos — Hardware Lab Technician**, at a desktop workstation monitoring the start of a lab session. He wants proof that all 32 configured nodes are represented and needs a precise explanation when one becomes silent.

## Trigger

The simulated telemetry generator starts periodic heartbeats for the canonical 32-node inventory, followed by a simulated clock advance for a node that stops reporting.

## Preconditions

- Canonical fixture contains 31 single-GPU workstations and one dual-GPU server.
- Each node has a configured positive heartbeat interval; its duration is configuration, not a UX-selected default (ODD-1).
- Fleet Dashboard is connected to the simulator and has no inventory validation error.

## Primary path

1. Carlos opens the Fleet Dashboard; inventory loading resolves into exactly 32 stable-position node cards.
2. Cards show node state, separate cordon status, last accepted heartbeat, freshness/elapsed interval count, temperature, VRAM, driver health, storage, maintenance, and read-only reservation indicator.
3. Accepted heartbeats update values in place. The summary and card announce state transitions, not every telemetry change.
4. Carlos pauses heartbeats for one node in Fault Injector and previews the generated silence condition.
5. At exactly three elapsed heartbeat intervals, the node does not transition because the authoritative boundary is strictly greater than three.
6. At an evaluation time greater than three intervals, the card transitions to `OFFLINE`, shows `CORDONED`, and retains `Last known` telemetry.
7. Carlos opens Node Detail to see last accepted time, configured interval reference, elapsed interval count, `ERR_SILENT`, decision time, and cited evidence/version.

## Failure path

- Malformed, duplicate, late, or unknown-node heartbeats are rejected without replacing last-known-good telemetry; the rejection explanation links to the affected field/rule.
- If inventory is empty or not 32 nodes, show a page-level configuration error rather than a healthy empty fleet.
- If the page loses its data connection, keep last-known values, mark them stale, and expose Retry.
- If connectivity alternates every five seconds, hold a stable primary state, show `CONNECTIVITY UNSTABLE` plus `CORDONED`, and update one alert episode. **OPEN DESIGN DECISION:** ODD-5/ODD-6 timing values are not displayed or inferred.

## System feedback

- Loading: inventory skeleton or “Loading fleet inventory…” announcement.
- Success: summary reads `32 nodes`; current accepted timestamps update without card movement.
- Silent transition: visible text/icon/color cue, persistent alert row, timeline entry, and polite live announcement.
- Explanation: “OFFLINE because elapsed silence is greater than 3 configured heartbeat intervals,” with actual evidence and rule ID.

## Surfaces involved

- Fleet Dashboard — primary monitoring and alert rail.
- Fault Injector — simulated pause/clock controls.
- Node Detail — evidence, last-known telemetry, and state timeline.

## State transitions

- Startup: `UNKNOWN → HEALTHY` or `DEGRADED` based on first accepted heartbeat.
- Silence: any unlocked state → `OFFLINE` only when elapsed time is `>3 × configured interval`.
- Return: `OFFLINE → RECOVERING`; never directly to `HEALTHY`.

## Success condition

Carlos can account for exactly 32 unique nodes, distinguish current from stale telemetry, observe no early transition at exactly three intervals, and explain the qualifying `OFFLINE`/cordon result from cited evidence.

## Traceability

- **FRs:** FR-1, FR-2, FR-3, FR-4, FR-7, FR-11, FR-12, FR-13.
- **NFRs:** NFR-1, NFR-4, NFR-5, NFR-6, NFR-7, NFR-9, NFR-10, NFR-13.

