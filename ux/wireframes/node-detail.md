---
title: Node Detail Wireframe
status: final
created: 2026-09-26
viewport: Desktop 1440px reference
---

# Node Detail — Editable Wireframe

Example uses the mandatory thermal scenario for `ws-gpu-14`.

```text
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [← Fleet]  ws-gpu-14 · Workstation · 1 × 24 GB GPU                         Evaluated 14:05:04   [Copy evidence]          │
│ ⚠ DEGRADED          ● ONLINE          🔒 CORDONED                           Last accepted HB 14:05:03                  │
├──────────────────────────────────────────────────────────────────────────────┬─────────────────────────────────────────────┤
│ WHY THIS CHANGED — CRITICAL                                                  │ OPERATIONAL CONTEXT                         │
│ HEALTHY → DEGRADED · cordon false → true                                     │                                             │
│ GPU 0 reported 88.1°C at 14:05:03, above the authoritative >88°C rule.       │ Maintenance lock: OFF                       │
│ Rule: ERR_THERMAL_88 · Evidence: hb-v00842 · Evaluated: 14:05:04             │ Observed lock: OFF                          │
│ No new-work eligibility is advertised. Existing work was not terminated.     │ Reservation refs: 1                         │
├───────────────────────────────────────┬──────────────────────────────────────┤ External/mock · read-only                   │
│ GPU TELEMETRY                         │ NODE TELEMETRY                       │                                             │
│                                       │                                      │ Active workload refs: 1                     │
│ GPU 0 temperature   88.1 °C  CRITICAL │ Driver health        HEALTHY         │ External/mock · read-only                   │
│ Threshold           >88 °C            │ Storage free          312 / 500 GB   │                                             │
│ VRAM occupied       8.0 / 24 GB       │ Boot/session          boot-A7        │ [Schedule maintenance]                      │
│ Sample version      hb-v00842          │ Event time            14:05:03       │ [Open Fault Injector for ws-gpu-14]         │
│                                       │ Receive time          14:05:03       │                                             │
│                                       │ Freshness             Current        │ Controls shown for Carlos fixture.          │
├───────────────────────────────────────┴──────────────────────────────────────┤ Alex receives read-only context.            │
│ ACTIVE / RETAINED REASONS                                                    │                                             │
│ [THERMAL_OVER_88 · active]  Clear policy: OPEN DESIGN DECISION (ODD-4)       │ Absent: kill, schedule, checkpoint,          │
│ Clearing another reason cannot clear this reason.                            │ reservation edit, force healthy.            │
├──────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────┤
│ STATE TIMELINE                                                               │ ALERT EPISODE                               │
│                                                                              │                                             │
│ 14:05:04  HEALTHY → DEGRADED · cordoned                                      │ CRITICAL · ERR_THERMAL_88                   │
│            Cause: GPU 0 88.1°C > 88°C · evidence hb-v00842                   │ Opened 14:05:04                             │
│                                                                              │ Last observed 14:05:04                      │
│ 14:04:58  HEALTHY held · heartbeat accepted · evidence hb-v00841             │ Update count 1                              │
│                                                                              │ [View episode evidence]                     │
│ 14:04:53  HEALTHY held · heartbeat accepted · evidence hb-v00840             │                                             │
└──────────────────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────┘
```

## Alternate-state substitutions

- `OFFLINE`: explain strict `>3 configured intervals`, show last-known telemetry and last accepted heartbeat.
- `RECOVERING`: show old/new boot-session evidence and “Recovery exit criteria: OPEN DESIGN DECISION (ODD-3),” with no progress percentage.
- `CONNECTIVITY UNSTABLE`: keep stable primary state, show raw five-second observations, one episode update count, and ODD-5/ODD-6 notice.
- `DRAINING`: show maintenance lock, external/mock workload IDs/count, no ETA, and no kill control.

