---
title: Scenario 3 — Simulated Workstation Reboot
status: final
created: 2026-09-26
---

# Scenario 3: Alex understands ws-gpu-05 recovery

## Protagonist

**Alex — Graduate Researcher**, checking why a workstation is unavailable after a lab student physically reboots it. Alex needs an accurate recovery explanation, not maintenance or scheduler controls.

## Trigger

The simulator changes `ws-gpu-05` from its current boot/session ID to a new value or sends the explicit state-loss marker.

## Preconditions

- `ws-gpu-05` has at least one accepted heartbeat with a known boot/session ID.
- The reboot event uses the normal telemetry validation path.
- ODD-3 recovery evidence remains unresolved and is not replaced by an invented count, duration, percentage, or ETA.

## Primary path

1. Telemetry for `ws-gpu-05` is interrupted; Fleet Dashboard labels retained values `Last known` without changing them to zero.
2. A new accepted heartbeat arrives with changed boot/session evidence.
3. The state machine creates exactly one `ERR_STATE_LOSS` transition to `RECOVERING` and sets `CORDONED`.
4. Alex opens the updated card and reaches Node Detail.
5. The recovery panel shows prior/new boot/session evidence, latest accepted heartbeat, current telemetry, reset ephemeral fields as `— Not reported`, and active reasons.
6. An evidence checklist distinguishes observed facts from unresolved exit criteria: “Recovery exit criteria: OPEN DESIGN DECISION (ODD-3).”
7. If the state machine later reports a resolved state using approved criteria, the UI shows that exact result and evidence; otherwise it remains `RECOVERING`.

## Failure path

- Replaying the older boot/session heartbeat is classified late and does not create another recovery transition.
- Missing or malformed state-loss evidence is rejected without fabricating a reboot.
- If silence exceeds three intervals before a current heartbeat returns, `OFFLINE` is shown; a returning current heartbeat moves to `RECOVERING`, not directly to `HEALTHY`.
- If thermal or driver reasons coexist, they remain visible and prevent a false healthy resolution.

## System feedback

- Transition line: “HEALTHY → RECOVERING · boot/session changed.”
- Explainability banner includes old/new evidence identifiers, evaluation time, and `ERR_STATE_LOSS`.
- Latest accepted heartbeat and raw evidence are visible without exposing an editable field.
- No progress bar, countdown, or “almost ready” copy is shown while ODD-3 is unresolved.

## Surfaces involved

- Fleet Dashboard — last-known freshness, `RECOVERING`, and cordon.
- Node Detail — state-loss evidence, recovery checklist, current telemetry, and timeline.
- Fault Injector — Carlos-only simulation support; Alex sees its resulting evidence, not mutation controls.

## State transitions

- Current unlocked state with new boot/session: `→ RECOVERING`, `cordoned=true`.
- Old replay: no transition.
- Qualifying silence: `RECOVERING → OFFLINE` according to precedence.
- Approved future recovery evidence and no active degradation: `RECOVERING → HEALTHY`; until then, no final healthy state is asserted.

## Success condition

Alex can identify that `ws-gpu-05` lost state/rebooted, see the latest accepted heartbeat and current evidence, understand why it is cordoned, and avoid a false recovery promise.

## Traceability

- **FRs:** FR-3, FR-6, FR-7, FR-11, FR-12, FR-13.
- **NFRs:** NFR-5, NFR-6, NFR-7, NFR-9, NFR-10, NFR-13.

