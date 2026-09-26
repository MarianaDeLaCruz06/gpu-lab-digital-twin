---
title: Fleet Dashboard — UX Specification
status: final
created: 2026-09-26
related_scenarios: [S-1, S-2, S-3, S-4]
---

# Fleet Dashboard

## Purpose and protagonist

Primary desktop monitoring surface for **Carlos** to assess fleet health and for **Alex** to understand node availability. It accounts for all 32 nodes without becoming the cross-platform observability console.

## Layout

At desktop width: application navigation left, fleet summary and node grid center, open-alert rail right. At narrower desktop/tablet widths, the alert rail moves below the grid. The grid follows `DESIGN.md` responsive rules and never auto-reorders on telemetry changes.

## Components

| ID | Component | Behavior |
|---|---|---|
| FD-01 | Page header | Title, simulator connection label, fleet evaluation/version, timezone/UTC offset, `Open Fault Injector` |
| FD-02 | Fleet summary | Counts total, `HEALTHY`, `DEGRADED`, `RECOVERING`, `OFFLINE`, `DRAINING`/`MAINTENANCE`, and cordoned; count filters grid |
| FD-03 | Search and filters | Node ID, class, state, cordon, reason; Clear filters remains visible |
| FD-04 | 32-node grid | Exactly one stable-position card per configured node |
| FD-05 | Node card | Identity, class, state, connectivity, cordon, telemetry, freshness, maintenance/reservation indicators, transition line |
| FD-06 | Alert rail | One open row per `(node_id, reason_code)` with severity, cause, times, update count, Inspect action |
| FD-07 | Global explanation notice | Inventory/connection errors and unresolved policy notices; never replaces per-node reason |

## Telemetry displayed

- Node ID and workstation/server class.
- Canonical state plus separate connectivity and `CORDONED` badge.
- Highest GPU temperature and GPU identifier.
- VRAM occupied/capacity per GPU.
- Driver health.
- Storage free/capacity.
- Last accepted heartbeat and freshness/elapsed interval count.
- Maintenance lock indicator.
- Reservation reference count with `External/mock · read-only` label.
- Active reason codes and latest transition summary.

Missing values are `— Not reported`; stale values are `Last known · [timestamp]`. Neither is zero-filled.

## State variants

| Variant | Presentation |
|---|---|
| `HEALTHY` + `ONLINE` | Healthy text/icon/color; no cordon; current accepted timestamp |
| `DEGRADED` | Warning state plus all reason chips; critical styling for thermal >88°C |
| `RECOVERING` | Recovery state, cordon, latest heartbeat, ODD-3 notice in detail |
| `OFFLINE` | Broken-link icon, cordon, last-known telemetry, `>3 intervals` explanation |
| `DRAINING` | Maintenance token, cordon, external/mock remaining workload count |
| `MAINTENANCE` | Wrench token, cordon, lock reason indicator |
| `UNKNOWN` | No accepted heartbeat; cordoned; no fabricated telemetry |
| Flapping | Stable primary state + `CONNECTIVITY UNSTABLE` + cordon; one updating alert episode |

## Buttons and actions

- Click/Enter node card: open Node Detail.
- Select summary count/filter: filter cards and announce result count.
- `Open Fault Injector`: opens simulation surface.
- `Inspect node` on alert: opens Node Detail focused on the alert reason.
- No reservation edit, job scheduling, workload termination, or bulk state mutation action.
- If a visible/focused node changes so it no longer matches an active filter, keep it in a `Changed outside current filter` strip with the transition reason until Carlos dismisses it or clears filters; do not make the card vanish during inspection.

## Validation behavior

- Inventory must render exactly 32 unique node cards and 33 GPU records. Any mismatch is a page-level configuration error.
- Fleet summary, card grid, and alert rail must share the same evaluation/version before the view is labeled current; otherwise retain the prior complete snapshot and show `Refreshing`.
- Filter/search accepts configured node IDs and known vocabulary; unknown query yields an empty-filter state, not an inventory error.
- The card cannot show `HEALTHY` if an unresolved driver mapping or other fail-closed reason is active.
- `ONLINE` is displayed only as connectivity, never as a canonical node state.

## Loading, empty, error, and success

- **Loading:** 32 stable skeleton cards when shape is known; otherwise named inventory-loading region. Background refresh keeps current values.
- **Empty:** only filters may be empty; show `No nodes match these filters` and Clear filters. Zero configured nodes is an error.
- **Error:** keep last-known data, label stale, show Retry and causal message; invalid sample never replaces current data. A disconnected simulator/stream shows `LIVE MONITORING INTERRUPTED`, disconnect time, and suppresses any “No open alerts” claim.
- **Success:** inventory count reads 32; accepted updates apply in place; state change yields durable transition line and alert/timeline record.

## Alerts

Critical thermal alerts are persistent and announced once assertively. Silent, flapping, and maintenance-drain issues are persistent warning rows. Repeated observations update one episode row rather than create new rows or toasts.

## Accessibility

- `main` label: `Fleet map, 32 nodes`; alert rail is complementary landmark.
- Node cards are buttons with accessible names summarizing ID, state, cordon, highest temperature, and freshness.
- Text/icon/color redundancy for every state.
- Keyboard order: header → summary → filters → grid in configured order → alerts.
- Updates that do not change state are not live-announced.
- At 200% zoom, alert rail moves below grid; no telemetry value is clipped.

## Traceability

FR-1–5, FR-7, FR-10–13; NFR-1, NFR-3–10, NFR-13.
