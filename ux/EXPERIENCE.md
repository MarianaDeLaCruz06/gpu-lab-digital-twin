---
name: Academic AI Compute Fabric — GPU Lab Digital Twin
status: final
created: 2026-09-26
updated: 2026-09-26
sources:
  - ../planning/prd.md
  - DESIGN.md
---

# GPU Lab Digital Twin — Experience Spine

## Foundation

Desktop-first responsive web prototype for an administrative/observability module. The canonical operational surface is a Fleet Dashboard backed entirely by simulated telemetry and fault controls. `DESIGN.md` owns visual tokens; this document owns information architecture, behavior, states, interactions, accessibility, and feedback. If a wireframe differs, these two spines win.

The UI distinguishes three concepts:

1. **Node state:** `UNKNOWN`, `HEALTHY`, `DEGRADED`, `RECOVERING`, `DRAINING`, `MAINTENANCE`, or `OFFLINE`.
2. **Connectivity/freshness:** `ONLINE`, `SILENT`, `CONNECTIVITY UNSTABLE`, or no accepted heartbeat. `ONLINE` is not a replacement for `HEALTHY`.
3. **Eligibility:** `CORDONED` or eligible for new work. The UI does not schedule work.

## Information Architecture

| Surface | Reached from | Purpose |
|---|---|---|
| Fleet Dashboard | Default route | Monitor all 32 nodes, summary counts, alerts, freshness, and filters |
| Node Detail | Node card or alert row | Inspect telemetry, exact state reason, timeline, and external/mock context |
| Fault Injector | Header action or node detail | Generate reproducible simulated heartbeat, thermal, reboot, silence, drain, and flapping inputs |
| Maintenance Control | Node detail for Carlos | Place/release a maintenance lock and monitor mocked workload drain |

Global navigation contains only Fleet, Alerts (dashboard rail anchor), and Fault Injector. Reservation creation, job scheduling, quota, catalog, and cross-platform reporting do not appear.

## Voice and Tone

Operational copy is factual, compact, and causal.

| Do | Don't |
|---|---|
| “Cordoned: GPU 0 reported 88.1°C, above the >88°C rule.” | “Something went wrong.” |
| “Last accepted heartbeat: 14:05:03. Silent after more than 3 configured intervals.” | “Node might be offline.” |
| “Maintenance lock active. Waiting for 2 external/mock workloads.” | “Draining jobs…” without count or provenance |
| “Simulation applied to ws-gpu-14.” | “Success!” |
| “OPEN DESIGN DECISION: stabilization timing is not approved.” | A fabricated countdown or ETA |

Use Carlos and Alex by name in scenario copy and documentation. Surface copy addresses the current operator as “you” only for confirmations; it never replaces named-protagonist coverage.

## Component Patterns

| Component | Behavioral contract |
|---|---|
| Fleet summary | Selecting a count filters cards without changing their order; result count and active filter are announced. |
| Node card | Opens Node Detail. Updates telemetry in place. A new state adds a non-color transition line and never causes automatic re-sort. |
| Freshness indicator | Shows last accepted timestamp, elapsed interval count when known, and `Last known` for stale values. Equality at 3 intervals is not silent; only `>3` qualifies. |
| Explainability banner | Always visible for non-healthy state, cordon, held transition, or rejected input. Contains result, cause, evidence time/version, rule ID, and next safe action/constraint. |
| Alert episode row | One open row per `(node_id, reason_code)`. Repeated observations increment update count and last-observed time. Closed episodes remain in the timeline. |
| Confirmation dialog | Names node, requested state change, immediate cordon effect, external/mock workload consequence, and what the module cannot do. Requires explicit Confirm/Cancel. |
| Fault preset | Preview lists generated inputs and expected evaluation route. Apply requires target confirmation; result links to the resulting transition/evidence. |
| Read-only external data | Reservation/workload values carry persistent `External/mock · read-only` text and expose no edit affordance. |

## State Patterns

### Loading

- Fleet Dashboard renders 32 card-shaped skeletons only after inventory shape is known; otherwise a single “Loading fleet inventory…” region is announced.
- Existing telemetry remains visible during background refresh with `Refreshing` beside the last accepted timestamp; values are not blanked.
- Controls that require a selected node remain disabled with a visible reason, not removed.
- Summary counts, cards, and alert rows carry one fleet evaluation/version label and commit as one visible snapshot. While a newer snapshot is assembling, the prior complete snapshot remains visible with `Refreshing`; mixed-version counts and cards are never presented as one current view.

### Empty

- A canonical configured fleet must contain 32 nodes; zero inventory is an error, not a normal empty state.
- Empty filtered result: “No nodes match these filters.” Keep active filters visible and provide `Clear filters`.
- Empty alert rail: “No open alert episodes.”
- Empty reservation/workload list: “None reported by external/mock source.”

### Success

- Successful simulation or maintenance command produces a concise confirmation near the initiating control and a durable timeline/decision entry.
- Success never implies health. Example: “Maintenance lock set; node is DRAINING and cordoned.”
- State resolution is shown only after the state machine reports it; the interface does not optimistically label a node `HEALTHY`.

### Error

- Validation errors remain adjacent to the offending field and list accepted format/range.
- Rejected telemetry or fault input preserves last-known-good values and shows rule code/evidence.
- Page-level read failure keeps last-known data where available, labels it `Last known`, exposes Retry, and announces the error once.
- Loss of the simulator/stream displays `LIVE MONITORING INTERRUPTED` with disconnect time and marks the entire fleet snapshot last known; the alert rail cannot claim “No open alerts” while monitoring is interrupted.
- `ERR_POLICY_UNRESOLVED` displays the exact ODD and preserves the state and cordon result defined for that policy's safe unresolved path; it does not universally force `cordoned=true`. For unresolved ODD-5, the existing cordon value is preserved. No default value or simulated resolution is implied.

### Degraded

`DEGRADED` uses `{colors.degraded}` plus warning icon and text. The reason banner lists every active degradation reason independently. Clearing one reason does not remove another. A thermal reason above 88°C escalates alert treatment to `{colors.critical}` while the canonical node state remains `DEGRADED` unless a higher-precedence state applies.

### Recovery

`RECOVERING` shows latest accepted heartbeat, current boot/session evidence, current telemetry, active reasons, and an evidence checklist. Because ODD-3 is unresolved, it shows “Recovery exit criteria: OPEN DESIGN DECISION” rather than a percentage or ETA. If the state machine later reports `HEALTHY`, the timeline records the evidence and rule used; the UX does not infer completion.

### Maintenance

- Lock activation immediately displays `CORDONED` and either `DRAINING` (mocked active workload count >0) or `MAINTENANCE` (count =0).
- Drain progress is count/list based, not a fabricated percentage or time estimate.
- A heartbeat/command lock mismatch displays `ERR_LOCK_SOURCE_MISMATCH`; Carlos's command record remains authoritative.
- Release confirmation warns that release triggers reevaluation and does not guarantee `HEALTHY`.

### Stale telemetry

Stale values retain their last accepted value, timestamp, and `Last known` prefix. They use `{colors.offline}` treatment plus text/icon. Missing values display `— Not reported`, never zero. Silence explanation shows configured interval symbolically and the observed elapsed interval count; the UI does not invent interval duration.

### Flapping-node feedback

For alternating online/offline observations every five seconds:

- Keep the last stable public state in the card's primary state position while evaluation is pending.
- While ODD-5 is unresolved, retain the last stable public connectivity and cordon values, show the latest raw observation and observation count on Node Detail, and show one current `ERR_POLICY_UNRESOLVED` diagnostic; do not show `CONNECTIVITY UNSTABLE` or create a flapping alert episode.
- If an approved ODD-5 policy later classifies the evidence, show `CONNECTIVITY UNSTABLE`, `CORDONED`, and one open `ERR_CONNECTIVITY_FLAPPING` episode; repeated qualifying observations update that row rather than add a toast or row.
- Do not pulse, flash, animate, reorder, or swap the primary label on every observation.
- Show `OPEN DESIGN DECISION: stabilization and repeat-alert timing (ODD-5/ODD-6)`; no countdown or hidden default.

### Fault-injection feedback

Fault injection has Preview → Confirm → Applied/Rejected states. Preview differentiates generated observation from expected result and warns that the state machine—not the UI preset—chooses final state. Applied feedback includes target, event/version ID, accepted/rejected result, resulting state/cordon, and link to Node Detail. Repeating a preset uses a fresh explicit confirmation.

## Alert Behavior and Severity

| Level | Use | Behavior |
|---|---|---|
| Critical | Thermal >88°C; safety-affecting trust failure | Persistent alert rail row, node banner, screen-reader announcement once per episode; no auto-dismiss |
| Warning | Driver degradation, flapping, drain blocked | Persistent row/banner; repeated observations update the same episode |
| Information | Recovery, maintenance completion, simulation accepted | Timeline plus inline confirmation; no interruptive alert unless action is required |

Severity is never color-only. Each alert includes severity word, icon, reason code, node, cause, opened/last-observed times, and update count. The system does not claim external notification delivery; ODD-6 remains open.

## Confirmation Behavior

- Require confirmation for maintenance lock, maintenance release, and every fault application.
- Do not require confirmation for filters, navigation, copying evidence, opening details, or previewing a fault.
- Dialog primary button states verb and target, e.g. `Lock [configured server ID] for maintenance`.
- `Escape`/Cancel leaves state unchanged. Confirm disables only while the command is pending and prevents duplicate submission.
- Every state-changing preview is bound to the target's displayed evaluation/version. If that version changes before confirmation, submission is stopped and the dialog requires a refreshed preview.
- If command transport ends without a definitive result, show `Outcome unknown`, disable retry, reconcile the authoritative command/timeline state, and then offer the action again only when the outcome is known.
- No control offers workload termination, checkpointing, rescheduling, reservation editing, or physical hardware action.

## Node-State Transition Feedback

Every transition generates three synchronized cues:

1. Card badge and transition line update without moving the card.
2. Relevant alert episode opens/updates/closes.
3. Node timeline appends prior state → result, cause, rule, evidence/version, and evaluation time.

Screen readers announce one concise transition summary. Raw telemetry changes that do not change state are not live-announced. When multiple conditions arrive together, the banner shows the selected state plus retained secondary reasons according to PRD precedence.

All event, receive, evaluation, command, and “last known” times display the simulated clock's explicit timezone name or UTC offset. Relative freshness may supplement but never replace the absolute timestamp.

## Interaction Primitives

- Mouse and keyboard parity for every control.
- `Enter`/`Space` activates focused cards and buttons; `Escape` closes the top dialog without changes.
- `/` focuses fleet search when no dialog is open; `f` opens filters only when focus is outside an input. Shortcuts are listed in accessible help and never the sole path.
- Tables support row navigation without trapping arrow keys; timeline is chronological and filterable.
- Tooltips supplement visible labels; they never contain the only explanation.
- Motion is limited to a nonessential refresh indicator. `prefers-reduced-motion` removes transitions; no flashing or pulsing status.

## Accessibility Floor — WCAG 2.1 AA

- Meet WCAG 2.1 AA; normal text contrast ≥4.5:1, large text and meaningful non-text graphics ≥3:1.
- All state, severity, freshness, and cordon signals combine visible text, icon/shape, and color.
- Focus order follows visual order; focus indicator uses `{components.focus-ring}` and is never obscured.
- Minimum pointer target is 44×44 CSS px, with compact visual controls allowed only inside that target area.
- Landmarks: header, navigation, main Fleet Map, complementary Alerts rail. Each has an accessible name.
- Live regions: `polite` for successful commands and state changes; `assertive` once for a new critical thermal episode. Repeated flapping updates do not repeatedly interrupt.
- At 200% zoom, content reflows without loss; below 768 px, unavailable maintenance mutations have explanatory text.
- Telemetry uses real text, not chart-only labels. Units and timestamps are included in accessible names.

## Responsive & Platform

Desktop is authoritative for Carlos's operational controls. Tablet preserves monitoring and simulation. Narrow screens preserve monitoring but intentionally disable maintenance mutation; this is a UX safety boundary, not an authorization system. Behavior follows `DESIGN.md` breakpoint rules.

## Key Flows

### Flow 1 — Carlos contains a thermal anomaly

Carlos sees one critical alert for `ws-gpu-14`, opens Node Detail, and reads that GPU 0 reported above 88°C. **Climax:** the screen pairs `DEGRADED` with `CORDONED` and the exact evidence/rule, proving that the node is excluded from new work without implying that active work was killed.

### Flow 2 — Alex understands a reboot recovery

Alex opens `ws-gpu-05` from the Fleet Dashboard after its boot/session changes. **Climax:** Node Detail shows `RECOVERING`, latest heartbeat, state-loss evidence, and an explicit unresolved recovery-exit policy rather than a false completion estimate.

### Flow 3 — Carlos drains the dual-GPU server

Carlos confirms a maintenance lock, watches the external/mock workload count move toward zero, and sees `DRAINING` become `MAINTENANCE`. **Climax:** completion feedback confirms lock ownership and zero active mocked workloads while offering no kill or scheduler control.

### Flow 4 — Carlos investigates unstable connectivity

Carlos sees the last stable public state/connectivity remain fixed as observations alternate every five seconds. **Climax:** raw observations and one current policy-unresolved diagnostic remain inspectable, while the UI creates no flapping alert flood and does not claim `CONNECTIVITY UNSTABLE` or change cordon until ODD-5 is approved.
