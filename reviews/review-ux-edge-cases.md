# UX Edge-Case Review — GPU Lab Digital Twin

Date: 2026-09-26  
Artifact reviewed: `ux/`  
Lens: BMad `edge-case-hunter`  
Artifact class: Behavioral UX document collection

## Verdict

Ten unhandled paths were found in the initial Phase 2 artifact set. Seven were accepted and applied, two were deferred because their numeric/product policy is already an explicit open design decision, and one was rejected because it would cross into scheduler ownership. No blocking Phase 2 finding remains.

## Findings and triage

### UX-EC-01 — Mixed-version fleet snapshot

- **Location:** `ux/pages/fleet-dashboard.md` — loading and update behavior
- **Trigger condition:** Summary updates before cards or alert rail finish updating.
- **Guard snippet:** Commit summary, cards, and alerts under one evaluation/version; retain prior snapshot meanwhile.
- **Potential consequence:** Carlos sees counts contradict the visible node states.
- **Classification:** **ACCEPT** — applied to `EXPERIENCE.md` and Fleet Dashboard.

### UX-EC-02 — Fault preview becomes stale

- **Location:** `ux/pages/fault-injector.md` — Preview → Confirm boundary
- **Trigger condition:** Target state changes after preview but before confirmation.
- **Guard snippet:** Bind preview to target version; invalidate and require re-preview on mismatch.
- **Potential consequence:** Carlos applies a fault using obsolete context.
- **Classification:** **ACCEPT** — applied to Fault Injector and confirmation behavior.

### UX-EC-03 — Maintenance preview races workload/state changes

- **Location:** `ux/pages/maintenance-control.md` — lock/release confirmation
- **Trigger condition:** Lock or workload snapshot changes before Carlos confirms.
- **Guard snippet:** Bind state, lock, and workload versions; refresh preview on any change.
- **Potential consequence:** Confirmation describes consequences that are no longer true.
- **Classification:** **ACCEPT** — applied to Maintenance Control.

### UX-EC-04 — Unknown command outcome permits unsafe retry

- **Location:** `ux/EXPERIENCE.md` confirmation; `ux/pages/maintenance-control.md` error state
- **Trigger condition:** Command transport fails after submission without returning a result.
- **Guard snippet:** Show outcome unknown, disable retry, reconcile authoritative record before re-enabling.
- **Potential consequence:** Duplicate or conflicting maintenance commands can be submitted.
- **Classification:** **ACCEPT** — applied globally and to Maintenance Control.

### UX-EC-05 — Already-locked node lacks a conflict path

- **Location:** `ux/pages/maintenance-control.md` — validation
- **Trigger condition:** Carlos requests a lock when an authoritative lock already exists.
- **Guard snippet:** Treat identical request as satisfied; reject conflicting reason; preserve existing record.
- **Potential consequence:** A second command obscures lock ownership and reason.
- **Classification:** **ACCEPT** — applied to Maintenance Control.

### UX-EC-06 — Timezone ambiguity in freshness evidence

- **Location:** `ux/EXPERIENCE.md` and timestamped surfaces
- **Trigger condition:** Event, receive, and evaluation times use unlabeled clock values.
- **Guard snippet:** Display simulated timezone name or UTC offset beside absolute timestamps.
- **Potential consequence:** Carlos misreads event order or heartbeat freshness.
- **Classification:** **ACCEPT** — applied to the experience spine and Fleet header contract.

### UX-EC-07 — Active filter hides a changing node

- **Location:** `ux/pages/fleet-dashboard.md` — filtered grid update
- **Trigger condition:** A focused node transitions out of the active filter.
- **Guard snippet:** Pin it in a changed-outside-filter strip until dismissal or filter clear.
- **Potential consequence:** The node vanishes while Carlos investigates its transition.
- **Classification:** **ACCEPT** — applied to Fleet Dashboard.

### UX-EC-08 — Alert acknowledgement policy is undefined

- **Location:** `ux/EXPERIENCE.md` — alert behavior
- **Trigger condition:** Carlos wants to acknowledge an open alert without closing its cause.
- **Guard snippet:** Decide whether acknowledgement exists, who owns it, and its effect on episodes.
- **Potential consequence:** Implementations may confuse acknowledgement with condition resolution.
- **Classification:** **DEFER** — alert delivery/repeat semantics remain ODD-6. Phase 2 deliberately offers inspect, not acknowledge; this does not block UX closure.

### UX-EC-09 — Timeline/history exhaustion is undefined

- **Location:** `ux/pages/node-detail.md` — state timeline
- **Trigger condition:** Retained records exceed one screen or the eventual retention limit.
- **Guard snippet:** Select pagination/window behavior after numeric retention capacity is approved.
- **Potential consequence:** Navigation or “complete history” claims become inconsistent.
- **Classification:** **DEFER** — PRD NFR-12 leaves duration/capacity open. UX makes no complete-history claim; implementation readiness must resolve it.

### UX-EC-10 — Add workload cancellation when drain stalls

- **Location:** `ux/pages/maintenance-control.md` — prolonged `DRAINING`
- **Trigger condition:** External/mock workload count never reaches zero.
- **Guard snippet:** Add force-cancel or scheduler takeover control.
- **Potential consequence:** Drain remains blocked without an in-module escape action.
- **Classification:** **REJECT** — job termination/scheduling belongs outside Module 3. UX correctly shows ODD-7 and no force action.

## Requested-check coverage

| Check | Result |
|---|---|
| Loading / Empty / Error / Success | Explicit in experience spine and all four page specs |
| Telemetry freshness / silent ambiguity | Absolute timestamps, timezone, last-known labels, strict `>3` boundary |
| Thermal ambiguity | Exact GPU/value, strict threshold, critical episode, cordon explanation |
| Dangerous action ambiguity | Preview/version binding and explicit confirmations; no force actions |
| Maintenance-drain confusion | Mock provenance, count/list progress, unknown-outcome reconciliation |
| Inaccessible/color-only status | Text + icon/shape + color, contrast and live-region contracts |
| Flapping flood / visual oscillation | Stable primary state and one updating episode; no repeated toasts |
| Scope creep | Force-cancel finding rejected; reservations/workloads remain read-only external/mock |
| PRD terminology | Canonical state names retained; `ONLINE` is connectivity only |
| Untestable behavior | Deferred numeric policies remain named ODDs with no fabricated values |

## Counts

- **Total:** 10
- **Accepted:** 7
- **Deferred:** 2
- **Rejected:** 1
- **Blocking findings remaining:** 0

