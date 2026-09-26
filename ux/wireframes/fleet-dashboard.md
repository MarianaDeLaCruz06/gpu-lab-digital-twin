---
title: Fleet Dashboard Wireframe
status: final
created: 2026-09-26
viewport: Desktop 1440px reference
---

# Fleet Dashboard — Editable Wireframe

Text wireframe; component behavior and tokens are governed by `../DESIGN.md` and `../EXPERIENCE.md`.

```text
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ GPU LAB DIGITAL TWIN                                      Simulator: CONNECTED     Evaluated 14:05:04   [Fault injector] │
├───────────────┬──────────────────────────────────────────────────────────────────────────────┬─────────────────────────────┤
│ NAV           │ FLEET SUMMARY                                                                │ OPEN ALERTS (3)             │
│               │ [32 Total] [26 Healthy] [2 Degraded] [1 Recovering] [1 Offline] [2 Maint]    │                             │
│ ● Fleet       │ [6 Cordoned]                                                                 │ CRITICAL                    │
│   Alerts      ├──────────────────────────────────────────────────────────────────────────────┤ ws-gpu-14 · THERMAL         │
│   Fault       │ Search node… [____________]  State [All ▾]  Cordon [All ▾]  [Clear filters]  │ 88.1°C > 88°C              │
│   injector    │ Showing 32 of 32                                                          │ Opened 14:05:03 · updates 1 │
│               ├───────────────────┬───────────────────┬───────────────────┬──────────────────┤ [Inspect node]              │
│               │ ws-gpu-01        │ ws-gpu-02        │ ws-gpu-03        │ ws-gpu-04       │                             │
│               │ ✓ HEALTHY        │ ✓ HEALTHY        │ ✓ HEALTHY        │ ✓ HEALTHY       │ WARNING                     │
│               │ ● ONLINE         │ ● ONLINE         │ ● ONLINE         │ ● ONLINE        │ ws-gpu-22 · SILENT          │
│               │ GPU 52°C         │ GPU 55°C         │ GPU 49°C         │ GPU 57°C        │ >3 configured intervals     │
│               │ VRAM 8/24 GB     │ VRAM 0/24 GB     │ VRAM 14/24 GB    │ VRAM 6/24 GB    │ Last seen 14:01:10          │
│               │ Driver healthy   │ Driver healthy   │ Driver healthy   │ Driver healthy  │ [Inspect node]              │
│               │ SSD 312/500 GB   │ SSD 420/500 GB   │ SSD 202/500 GB   │ SSD 390/500 GB  │                             │
│               │ HB 2s ago        │ HB 1s ago        │ HB 2s ago        │ HB 3s ago       │ WARNING                     │
│               ├───────────────────┼───────────────────┼───────────────────┼──────────────────┤ ws-gpu-09 · FLAPPING        │
│               │ ws-gpu-05        │ ws-gpu-06        │ ws-gpu-07        │ ws-gpu-08       │ CONNECTIVITY UNSTABLE       │
│               │ ↻ RECOVERING     │ ✓ HEALTHY        │ ✓ HEALTHY        │ ✓ HEALTHY       │ observations 12             │
│               │ 🔒 CORDONED      │ ● ONLINE         │ ● ONLINE         │ ● ONLINE        │ one open episode            │
│               │ Latest HB 1s ago │ GPU 61°C         │ GPU 48°C         │ GPU 59°C        │ ODD-5/ODD-6 OPEN            │
│               │ State loss       │ VRAM 4/24 GB     │ VRAM 0/24 GB     │ VRAM 9/24 GB    │ [Inspect node]              │
│               │ ODD-3 OPEN       │ Driver healthy   │ Driver healthy   │ Driver healthy  │                             │
│               ├───────────────────┼───────────────────┼───────────────────┼──────────────────┤                             │
│               │ ws-gpu-09        │ ws-gpu-10        │ ws-gpu-11        │ ws-gpu-12       │ ALERT RULE                  │
│               │ ⚠ DEGRADED       │ ✓ HEALTHY        │ ✓ HEALTHY        │ ✓ HEALTHY       │ One open row per            │
│               │ CONNECTIVITY     │ ● ONLINE         │ ● ONLINE         │ ● ONLINE        │ (node, reason). Repeated     │
│               │ UNSTABLE         │ …telemetry…      │ …telemetry…      │ …telemetry…     │ observations update count;  │
│               │ 🔒 CORDONED      │                  │                  │                 │ no repeated toasts.         │
│               ├───────────────────┼───────────────────┼───────────────────┼──────────────────┤                             │
│               │ ws-gpu-13        │ ws-gpu-14        │ ws-gpu-15        │ ws-gpu-16       │                             │
│               │ ✓ HEALTHY        │ ⚠ DEGRADED       │ ✓ HEALTHY        │ ✓ HEALTHY       │                             │
│               │ ● ONLINE         │ 🔥 88.1°C GPU 0  │ ● ONLINE         │ ● ONLINE        │                             │
│               │ …telemetry…      │ 🔒 CORDONED      │ …telemetry…      │ …telemetry…     │                             │
│               │                  │ Why: >88°C rule  │                  │                 │                             │
│               ├───────────────────┼───────────────────┼───────────────────┼──────────────────┤                             │
│               │ ws-gpu-17        │ ws-gpu-18        │ ws-gpu-19        │ ws-gpu-20       │                             │
│               │ …telemetry…      │ …telemetry…      │ …telemetry…      │ …telemetry…     │                             │
│               ├───────────────────┼───────────────────┼───────────────────┼──────────────────┤                             │
│               │ ws-gpu-21        │ ws-gpu-22        │ ws-gpu-23        │ ws-gpu-24       │                             │
│               │ …telemetry…      │ ⨯ OFFLINE        │ …telemetry…      │ …telemetry…     │                             │
│               │                  │ 🔒 CORDONED      │                  │                 │                             │
│               │                  │ Last known       │                  │                 │                             │
│               ├───────────────────┼───────────────────┼───────────────────┼──────────────────┤                             │
│               │ ws-gpu-25        │ ws-gpu-26        │ ws-gpu-27        │ ws-gpu-28       │                             │
│               │ …telemetry…      │ …telemetry…      │ …telemetry…      │ …telemetry…     │                             │
│               ├───────────────────┼───────────────────┼───────────────────┼──────────────────┤                             │
│               │ ws-gpu-29        │ ws-gpu-30        │ ws-gpu-31        │ DUAL-GPU SERVER │                             │
│               │ …telemetry…      │ …telemetry…      │ …telemetry…      │ ⇣ DRAINING      │                             │
│               │                  │                  │                  │ 🔒 CORDONED      │                             │
│               │                  │                  │                  │ 2 mock workloads│                             │
└───────────────┴───────────────────┴───────────────────┴───────────────────┴──────────────────┴─────────────────────────────┘
```

## Wireframe annotations

1. Every one of the 32 configured nodes occupies a stable grid cell: `ws-gpu-01` through `ws-gpu-31` plus the configured dual-GPU server.
2. `ONLINE` is connectivity; canonical state is separately shown.
3. The alert rail is durable and deduplicated; it is not a toast stack.
4. Cards keep the highest-risk current fact visible but provide Node Detail for complete evidence.
5. Ellipses stand for the same required card anatomy, not omitted nodes or optional telemetry.

