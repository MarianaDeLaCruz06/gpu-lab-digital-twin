# Impl-1 Review Checklist (review → done)

For: Mariana. Goal: independently accept or reject stories 1-1, 1-3 and 2-1 before they move from `review` to `done` in `docs/sprint-status.yaml`. Expected time is 45–60 minutes.

## 0. Set up (5 min)

```bash
git pull
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest                            # expect: 130 passed, 0 failed, 0 skipped
ruff check src tests migrations   # expect: All checks passed!
docker compose up --build         # optional: then open http://localhost:8000/docs
```

## 1. Decisions to confirm first

These changed or interpreted *your* Plan-2/Solu-2 design. If you disagree with any, stop and tell Julian before reviewing code.

| # | Decision | Where it is recorded |
|---|---|---|
| A | Our OpenAPI and AD-n take precedence over the task annex: `POST /v1/nodes/{nodeId}/heartbeats` returns 200 (not 202); thermal is strictly `> 88` → `DEGRADED` + cordon (not `>= 88` → `CORDONED_THERMAL`) | `docs/ai-decision-log.md` I1-DL-02, `walkthrough-impl1.md` §1 |
| B | OpenAPI 1.1.0 adds `/health`, `/ready` and `GET /v1/nodes` (from ARCHITECTURE §9.4) | `docs/contracts/openapi.yaml` |
| C | `ports/in` / `ports/out` renamed to `ports/inbound` / `ports/outbound` (`in` is a Python keyword) | I1-DL-03 |
| D | Seeded nodes start `UNKNOWN` + cordoned (FR-1), not `HEALTHY` as in `test/fixtures/seed_fleet.py` | I1-DL-04 |
| E | ODD-1 resolved as a 10 s heartbeat interval (from the annex), stored per node in `fixtures/fleet.json` | I1-DL-06 |
| F | Canonical heartbeat outcomes are implemented: `APPLIED`, `DUPLICATE`, `LATE_IGNORED`, and proven succession as `BOOT_CHANGE_DETECTED`; unproven succession remains `ERR_BOOT_SUCCESSION`. The server Clock is the authoritative receive time. | B02 remediation; `planning/detailed-design/contracts.md` P-H3/P-H6/P-H7 and AD-6 |
| G | Story 1.3 D1: silence is detected by an in-process scan every 5 s (no clock-tick endpoint). D2: a heartbeat after `OFFLINE` gives `RECOVERING`, never `HEALTHY` | spec 1-3, Decisions |
| H | Story 2.1 D1: `cordoned=true` is the "refuse placement" signal; no eligibility endpoint | spec 2-1, Decisions |

## 2. Per-story review

For each story, read the spec's frozen Intent, I/O matrix and Review Triage Log first, then the diff.

### Story 1-1 — heartbeat ingestion + fleet view (annex 3.1)

- **Diff:** commit `0b3f965` · **Spec:** `docs/spec-1-1-see-the-complete-simulated-fleet.md`
- **Look closely at:**
  - `src/gpu_lab_twin/application/heartbeat_service.py`: validation and the clock read happen under the write lock; duplicate vs. conflict handling.
  - `src/gpu_lab_twin/adapters/db/node_repository.py`: the `commit_heartbeat` single transaction, the revision CAS (`_compare_and_set`), and the alert upsert on the partial unique index.
  - `src/gpu_lab_twin/domain/node_state.py`: the reducer precedence and the "non-HEALTHY ⇒ cordoned" rule.
- **Check:**
  - [ ] Every rejection returns `ErrorBody` and changes nothing. Tests use `effect_probe`.
  - [ ] An identical replay returns `DUPLICATE` with the recorded response. The same `eventId` with a different payload returns 409.
  - [ ] Older/non-increasing telemetry returns `LATE_IGNORED`, is persisted as non-current evidence, and cannot overwrite the projection.
  - [ ] Proven boot succession returns and persists `BOOT_CHANGE_DETECTED`, increments the evidence epoch, and enters `RECOVERING`.
  - [ ] `GET /v1/nodes` lists 32 nodes, and readings never received are `null`, never 0.
  - [ ] Annex scenario test: `test_valid_heartbeat_updates_node_and_receive_time`.

### Story 1-3 — silent node → OFFLINE (annex 3.2)

- **Diff:** commit `16c4d80` · **Spec:** `docs/spec-1-3-detect-silence-at-the-exact-boundary.md`
- **Look closely at:**
  - `src/gpu_lab_twin/domain/heartbeat_policy.py::is_silent`: strict `>` on `timedelta`.
  - `src/gpu_lab_twin/application/liveness_service.py`: instants must advance, failures are isolated per node, and the configured inventory interval is used.
  - The OFFLINE → RECOVERING path in `heartbeat_service.py`.
- **Check:**
  - [ ] Exactly 30 s is not silent; 30.001 s is (`test_exactly_three_intervals_is_not_silent`, `test_just_past_three_intervals_is_silent`).
  - [ ] Nodes that never reported stay `UNKNOWN`.
  - [ ] An already-OFFLINE node is held with no new rows.
  - [ ] Annex scenario test: `test_silent_node_goes_offline_cordoned_with_alert_and_explanation`.

### Story 2-1 — thermal cordon (annex 3.3)

- **Diff:** commit `74cb068` · **Spec:** `docs/spec-2-1-cordon-an-overheating-workstation.md`
- **Look closely at:**
  - `reasons_from` in `heartbeat_policy.py` (`THERMAL_THRESHOLD_C`).
  - Measurement quantization in `api/schemas.py` (`_stored`).
  - The retained-thermal explanation in `domain/explanation.py`.
- **Check:**
  - [ ] 88.0 does not trigger; 88.1 and 91 trigger.
  - [ ] One hot server GPU cordons the whole node, and the explanation names that GPU.
  - [ ] After cooling, the node stays cordoned and cites ODD-4 plus the activating reading.
  - [ ] Annex scenario test: `test_thermal_emergency_cordons_immediately_and_is_visible_as_unavailable`.

## 3. Cross-cutting checks

- [ ] `tests/unit/test_architecture.py` passes: `domain/`, `ports/` and `application/` do not import FastAPI, SQLAlchemy, adapters, or the wall clock.
- [ ] `migrations/versions/0001_initial_twin_schema.py` and ORM metadata match the canonical Solu-2 schema, including `maintenance_locks`, its FK/check/unique constraints, timestamps, and one-active-lock partial unique index.
- [ ] `docs/deferred-work.md` has 3 items, all for later stories (1.2 / 2.2). Confirm none blocks Impl-1.
- [ ] `docs/ai-decision-log.md` attributes the AI work to Julian. Add yourself as reviewer if the course requires pair attribution.

## 4. Human review verdict — 2026-10-26

Reviewer: **Mariana De La Cruz (A00399618)**.

Mariana reviewed the Human Review Packet after B01 and B02 remediation. Current verification evidence is **130 passed, 0 failed, 0 skipped; Ruff lint and format checks pass**.

| Story | Decision | Rationale / remaining concern |
|---|---|---|
| 3.1 / 1-1 — Heartbeat ingestion | **APPROVED WITH MINOR DOCUMENTATION CONCERN** | Implementation is contract-compliant after B01/B02. The checklist, walkthrough, and governance records required correction for the former boot behavior, deferred `maintenance_locks`, and 126-test count. |
| 3.2 / 1-3 — Silent node detection | **APPROVED** | Strict `>3×interval`, idempotent OFFLINE transition, persistence, and recovery behavior are supported by automated evidence. |
| 3.3 / 2-1 — Thermal cordon | **APPROVED** | Canonical strict `>88°C` rule, cordon, explanation, persistence, and duplicate-alert containment are supported by automated evidence. |

**Technical blockers remaining: 0.** B01 (canonical schema/`maintenance_locks`) and B02 (canonical heartbeat dispositions) are resolved. This section records the actual decision made on 2026-10-26; it does not assert an earlier approval.
