---
title: Scenario 4 — Maintenance Drain
status: final
created: 2026-09-26
---

# Scenario 4: Carlos drains the dual-GPU server for maintenance

## Protagonist

**Carlos — Hardware Lab Technician**, preparing the one dual-GPU 48 GB-per-GPU server for physical maintenance. He needs to stop new work, observe external/mock active workloads, and confirm safe maintenance state without receiving scheduler or kill controls.

## Trigger

Carlos opens Maintenance Control for the canonical dual-GPU server and requests a maintenance lock with a non-empty reason.

## Preconditions

- The target is the configured server with two 48 GB GPUs.
- Latest state, maintenance command record, and external/mock active workload snapshot are visible.
- Carlos is represented by the prototype fixture; production identity/RBAC is external to Module 3.

## Primary path

1. From Node Detail, Carlos selects `Schedule maintenance` and reaches Maintenance Control.
2. He enters a reason; the preview names the server, immediate cordon effect, current external/mock workload count/IDs, and the fact that Module 3 cannot terminate, checkpoint, or reschedule them.
3. Carlos confirms `Lock [server ID] for maintenance`.
4. The node immediately becomes `CORDONED`. With active workload count above zero, the state is `DRAINING`.
5. The progress region shows count/list changes from subsequent mocked workload snapshots, with `External/mock · read-only` provenance and no fabricated percentage or ETA.
6. When the accepted mocked active workload count reaches zero, state transitions once to `MAINTENANCE`.
7. Carlos sees a durable completion message, active lock record, reason, zero workloads, and state timeline evidence.

## Failure path

- Empty maintenance reason prevents confirmation and focuses the field with an error.
- A conflicting heartbeat lock observation opens `ERR_LOCK_SOURCE_MISMATCH`; Carlos's command record remains authoritative and the lock stays active.
- If workloads never reach zero, state remains `DRAINING`; ODD-7 drain timeout/failure policy is shown as open, and no force action appears.
- If thermal, silence, driver, reboot, or flapping evidence coexists, it remains visible as a retained reason.
- Release reevaluates all conditions and never promises `HEALTHY`.

## System feedback

- Pending command disables duplicate confirmation while preserving Cancel until submission begins.
- Inline success: “Maintenance lock set; server is DRAINING and cordoned.”
- Progress: explicit remaining count and IDs, last external/mock update time, no percentage.
- Completion: “MAINTENANCE · lock active · 0 external/mock active workloads.”
- Timeline records lock command, drain updates, completion, and any mismatch.

## Surfaces involved

- Node Detail — entry point and retained health reasons.
- Maintenance Control — reason, preview, confirmation, progress, and release.
- Fleet Dashboard — server card and maintenance summary count.

## State transitions

- Lock with active workloads: any state → `DRAINING`, `cordoned=true`.
- Lock with zero active workloads: any state → `MAINTENANCE`, `cordoned=true`.
- `DRAINING → MAINTENANCE` only when mocked active workload count reaches zero.
- Release: reevaluate PRD precedence; target may be `OFFLINE`, `RECOVERING`, `DEGRADED`, `HEALTHY`, or another safe held result.

## Success condition

Carlos can prove the server is locked, cordoned, and free of reported active mocked workloads before maintenance, with no scope-leaking scheduler or termination action.

## Traceability

- **FRs:** FR-7, FR-8, FR-9, FR-11, FR-12, FR-13.
- **NFRs:** NFR-2, NFR-6, NFR-7, NFR-10, NFR-13.

