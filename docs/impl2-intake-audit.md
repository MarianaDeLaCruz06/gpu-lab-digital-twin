# Impl-2 Intake Audit

Date: 2026-11-07. Branch: `feature/impl2`. Baseline HEAD: `3abc6f2dc4001a8bb3d72d3fd70ad7eb1d504017`.

## Baseline

`uv run pytest -q -ra` completed before Story 3.4 artifacts or production code were changed: **130 passed, 0 failed, 0 skipped** in 10.43 seconds. The task PDF, Plan-2/Solu-2 artifacts, Impl-1 walkthrough/governance, source, tests, and migration were inspected. The declared dev dependencies include pytest, hypothesis, branch coverage, and Ruff; `pytest-asyncio` is not declared or currently required because the suite uses synchronous service tests and `asyncio.run` where applicable.

## Reusable Architecture

- Ports & Adapters layers with framework-free domain/application code and an explicit composition root.
- One process-wide write lock plus repository revision CAS for ordered atomic mutations.
- `Clock` outbound port and deterministic `FakeClock` with explicit `advance`/`set` capability.
- Existing node projection separates `NodeState`, `ConnectivityStatus`, and `cordoned` eligibility.
- Existing `alerts_one_open_per_reason_uq` partial unique index and atomic upsert provide episode/diagnostic deduplication.
- Existing audit ledger has a unique `event_id`, suitable for immutable connectivity evidence and duplicate protection.

## Canonical Flapping Behavior

AD-5 and Story 2.3 make raw connectivity observations evidence-only while ODD-5 is unresolved. The required stable baseline is: unchanged public state/connectivity/cordon, zero `ERR_CONNECTIVITY_FLAPPING` alerts, and at most one current `ERR_POLICY_UNRESOLVED` diagnostic. There is no hidden debounce or numeric threshold.

Four material Annex/canonical conflicts were recorded: (1) new `FLAPPING_CORDONED` state versus the closed state vocabulary, (2) `>3/60s` entry timing versus unresolved ODD-5, (3) one flapping incident versus zero flapping alerts plus one unresolved diagnostic, and (4) forced quarantine/new-work blocking versus the required unchanged stable cordon/eligibility tuple while classification is unresolved. The Annex node example is already canonical (`ws-gpu-14`), and no duplicate endpoint was introduced.

`FLAPPING_CORDONED` **does not exist** in the canonical state model and must not be added. If ODD-5 is later approved and classifies flapping, canonical representation is `DEGRADED` plus `cordoned=true`, active reason `ERR_CONNECTIVITY_FLAPPING`, and `CONNECTIVITY_UNSTABLE`, unless a higher-precedence state applies.

## Capability Audit

1. Alert deduplication: present through one-open-row partial uniqueness and atomic upsert; clear hysteresis for flapping remains ODD-5/ODD-6 and is intentionally unresolved.
2. Clock/FakeClock: present and adequate; no real sleeps are needed.
3. UI/frontend: no frontend/package manifest or browser UI exists; API read models only.
4. k6: no script, package, or CI scaffold exists. Deferred to Story 3.5 Flow D.
5. Playwright: no package/config/tests exist. Deferred to Story 3.6 Flow E.

## Impl-2 Gaps

- No connectivity observation domain value/policy, inbound port, application service, or repository transaction exists.
- No executable Story 3.4 acceptance tests or RED evidence exists.
- Connectivity observations need idempotent atomic persistence and one unresolved diagnostic without changing the public projection.
- Sprint tracking does not yet expose the six assignment story aliases 3.1-3.6.
- Impl-2 flow/governance/presentation evidence is not initialized.
- k6 and Playwright are absent, but adding them now would implement or scaffold later stories beyond Run 1's necessary scope.
