---
name: Academic AI Compute Fabric — GPU Lab Digital Twin
description: Desktop-first operational interface for monitoring and safely manipulating a simulated 32-node GPU fleet.
status: final
created: 2026-09-26
updated: 2026-09-26
sources:
  - ../planning/prd.md
colors:
  surface-base: '#F4F7FB'
  surface-panel: '#FFFFFF'
  surface-subtle: '#EAF0F7'
  ink-primary: '#172033'
  ink-secondary: '#4B5A73'
  border-default: '#B7C3D4'
  focus: '#005FCC'
  focus-contrast: '#FFFFFF'
  online: '#176B3A'
  online-bg: '#E5F4EA'
  degraded: '#8A4B00'
  degraded-bg: '#FFF0D5'
  recovering: '#005EA8'
  recovering-bg: '#E1F0FF'
  offline: '#4E5868'
  offline-bg: '#E8EBEF'
  maintenance: '#5B3F8C'
  maintenance-bg: '#EFE8FA'
  critical: '#B42318'
  critical-bg: '#FDE7E5'
  cordoned: '#7A271A'
  cordoned-bg: '#F9E7E3'
  unknown: '#5A6170'
  unknown-bg: '#ECEEF2'
typography:
  heading-xl:
    fontFamily: 'Inter, Segoe UI, sans-serif'
    fontSize: 24px
    fontWeight: '700'
    lineHeight: '1.25'
  heading-md:
    fontFamily: 'Inter, Segoe UI, sans-serif'
    fontSize: 18px
    fontWeight: '700'
    lineHeight: '1.35'
  body:
    fontFamily: 'Inter, Segoe UI, sans-serif'
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  label:
    fontFamily: 'Inter, Segoe UI, sans-serif'
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1.4'
  telemetry:
    fontFamily: 'JetBrains Mono, Consolas, monospace'
    fontSize: 13px
    fontWeight: '500'
    lineHeight: '1.45'
rounded:
  sm: 4px
  md: 6px
  lg: 8px
  full: 9999px
spacing:
  '1': 4px
  '2': 8px
  '3': 12px
  '4': 16px
  '5': 24px
  '6': 32px
  '8': 48px
  page-gutter: 24px
  grid-gap: 12px
components:
  node-card:
    background: '{colors.surface-panel}'
    border: '{colors.border-default}'
    radius: '{rounded.md}'
    gap: '{spacing.2}'
  status-badge:
    radius: '{rounded.sm}'
    font: '{typography.label}'
  alert-row:
    background: '{colors.surface-panel}'
    border: '{colors.border-default}'
    radius: '{rounded.sm}'
  focus-ring:
    color: '{colors.focus}'
    width: '3px'
    offset: '2px'
---

# GPU Lab Digital Twin — Design Spine

## Brand & Style

The interface is an operations instrument: dense, calm, inspectable, and explicit. Hierarchy comes from alignment, typography, borders, and status tokens—not decoration. Current fleet risk must be readable before brand personality. Every automated state has adjacent text explaining the reason, and every status uses text plus shape/icon plus color.

The visual posture is “lab control panel,” not consumer dashboard: flat panels, compact data rows, stable positions, monospaced telemetry, and no ornamental gradients, illustrations, glass effects, or motion that competes with changing metrics.

## Colors

- `{colors.surface-base}` is the application canvas; `{colors.surface-panel}` holds cards, tables, and rails.
- `{colors.ink-primary}` carries node identity and current values; `{colors.ink-secondary}` carries units, timestamps, and provenance.
- `{colors.online}` means a current connectivity observation or healthy/eligible result. The word `ONLINE` or `HEALTHY` must always accompany it.
- `{colors.degraded}` marks `DEGRADED` and warning-level telemetry. It never clears or overrides `{colors.critical}`.
- `{colors.recovering}` marks `RECOVERING` and progress/evidence still being gathered.
- `{colors.offline}` marks `OFFLINE` and unavailable/stale facts.
- `{colors.maintenance}` marks `DRAINING` and `MAINTENANCE`; the precise word differentiates the two states.
- `{colors.cordoned}` is a separate eligibility marker. A node may show it beside any non-healthy state; it is never represented only by a colored border.
- `{colors.critical}` is reserved for thermal safety, rejected input that affects trust, and actions that could alter operational state.
- Status foreground/background pairs must meet WCAG 2.1 AA contrast: at least 4.5:1 for normal text and 3:1 for large text and non-text indicators. Implementations must verify rendered pairs rather than infer contrast from token names.

### Status signatures

| Meaning | Text | Icon/shape | Token pair |
|---|---|---|---|
| Current connection | `ONLINE` | filled circle + check | `{colors.online}` / `{colors.online-bg}` |
| Health anomaly | `DEGRADED` | warning triangle | `{colors.degraded}` / `{colors.degraded-bg}` |
| Recovery evidence pending | `RECOVERING` | circular-arrow icon | `{colors.recovering}` / `{colors.recovering-bg}` |
| Silent/unreachable | `OFFLINE` | broken-link icon | `{colors.offline}` / `{colors.offline-bg}` |
| Active drain | `DRAINING` | down-arrow into tray | `{colors.maintenance}` / `{colors.maintenance-bg}` |
| Maintenance locked | `MAINTENANCE` | wrench icon | `{colors.maintenance}` / `{colors.maintenance-bg}` |
| Ineligible for new work | `CORDONED` | lock icon + outlined badge | `{colors.cordoned}` / `{colors.cordoned-bg}` |
| Connectivity flapping | `CONNECTIVITY UNSTABLE` | bidirectional broken-link icon | `{colors.degraded}` / `{colors.degraded-bg}` |
| No accepted heartbeat | `UNKNOWN` | question-mark diamond | `{colors.unknown}` / `{colors.unknown-bg}` |

## Typography

Use Inter with Segoe UI fallback for interface copy and JetBrains Mono with Consolas fallback for node IDs, timestamps, temperatures, capacities, reason codes, and raw values. Tabular numerals are required in summary counts and telemetry columns so updates do not shift alignment.

- `{typography.heading-xl}`: page title only.
- `{typography.heading-md}`: section and panel titles.
- `{typography.body}`: explanations, actions, and prose.
- `{typography.label}`: status badges, field names, column headings; sentence case, not all caps except canonical state values.
- `{typography.telemetry}`: data values; always show units (`°C`, `GB`, interval count) and never encode missing data as `0`.

Text scales to 200% without clipped controls or loss of content. Telemetry tables may scroll horizontally only below the desktop target; node identity and status remain pinned and readable.

## Layout & Spacing

The desktop shell uses a 12-column grid with `{spacing.page-gutter}` outer gutters and `{spacing.grid-gap}` internal gaps. At 1440 px, navigation occupies 2 columns, the primary Fleet Map 7 columns, and the alert/activity rail 3 columns. Dense content uses the 4/8/12/16/24/32/48 spacing scale; unrelated groups receive at least `{spacing.4}` separation.

### Responsive rules

| Viewport | Grid behavior | Operational behavior |
|---|---|---|
| ≥1280 px | Four node cards per primary-grid row; persistent alert rail | Full monitoring and Carlos controls |
| 1024–1279 px | Three cards per row; alert rail becomes a lower full-width region | Full monitoring and Carlos controls |
| 768–1023 px | Two cards per row; left navigation collapses | Read and fault-injection controls remain; confirmations use full-width dialog |
| <768 px | One card per row; summary and filters stack | Monitoring remains readable; maintenance mutation is unavailable with a message to use a desktop viewport |

No breakpoint hides current state, cordon, heartbeat freshness, temperature, or the reason link. Cards reflow; they do not shrink telemetry below `{typography.telemetry.fontSize}`.

## Elevation & Depth

Use borders and tonal surfaces. Persistent panels have no shadow. Dialogs and temporary popovers may use one low-elevation shadow to show modal ownership. Alerts are rows in a stable rail, not floating toast stacks; a short-lived toast may confirm an operator command but never replace the durable alert or transition record.

## Shapes

Corners are restrained: `{rounded.sm}` for badges and inputs, `{rounded.md}` for cards and tables, `{rounded.lg}` for dialogs. Pills are limited to compact filters, never status badges; different status shapes help non-color recognition. Icons use a consistent 1.5–2 px stroke and always have adjacent visible text.

## Components

### Fleet summary

A single row of labeled counts for total nodes, `HEALTHY`, `DEGRADED`, `RECOVERING`, `OFFLINE`, maintenance-related states, and cordoned nodes. Counts are buttons that apply a filter and announce the result count.

### Node card

`{components.node-card}` has four stable zones: identity and class; state plus separate cordon badge; critical telemetry; heartbeat freshness and indicators. State changes update in place and add a textual “Changed from X because Y” line; the card never jumps to another grid position unless Carlos changes sort/filter.

Minimum card content: node ID, workstation/server class, state, connectivity, cordon, highest GPU temperature, VRAM occupied/capacity per GPU, driver health, storage free/capacity, last accepted heartbeat, maintenance lock, and read-only reservation indicator.

### Status badge

`{components.status-badge}` combines icon, canonical state text, and color pair. Cordon is rendered as a second badge rather than appended to the health-state string.

### Alert row

`{components.alert-row}` shows severity word, node ID, reason code, plain-language reason, opened/last-observed times, update count, and “Inspect node.” Repeated equivalent observations update one row; they do not create a vertically growing toast stack.

### Telemetry table

Right-aligned tabular values, left-aligned labels, explicit units, and source/freshness metadata. Missing is `— Not reported`; stale is `Last known` plus timestamp. Neither is shown as zero.

### Actions

- Primary: one context-specific action per surface, using `{colors.focus}`.
- Secondary: bordered controls for filters, copy, and navigation.
- Operational: maintenance lock/release and fault injection use explicit verb + target.
- Destructive-looking styling is reserved for state-changing simulation or lock release confirmations; this prototype never presents job kill, checkpoint, or scheduling actions.

## Do's and Don'ts

| Do | Don't |
|---|---|
| Keep card zones and grid order stable while data updates | Re-sort cards automatically on every state change |
| Show state text, icon, and color together | Encode state or severity by color alone |
| Label timestamps as accepted, observed, or last known | Show an unlabeled “Updated” time |
| Show read-only `External/mock` labels on reservations/workloads | Make reservation or workload rows look editable |
| Keep explanations adjacent to state changes | Hide reasons behind an unlabeled icon or tooltip only |
| Use one durable alert episode per node and reason | Spawn one toast for every flapping observation |
| Display `OPEN DESIGN DECISION` where stabilization timing is unresolved | Invent a countdown, debounce value, or recovery estimate |
| Preserve telemetry density with alignment and compact spacing | Add decorative charts, gradients, illustrations, or animation |

