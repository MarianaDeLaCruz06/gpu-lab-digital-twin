# GPU Lab Digital Twin

Module 3 of the **Academic AI Compute Fabric** a standalone, hardware-agnostic digital twin of the university GPU lab: 31 workstations with one 24 GB GPU each and one server with two 48 GB GPUs (32 nodes, 33 GPUs, 840 GB VRAM). All telemetry is simulated; no NVIDIA hardware, CUDA, or other team's module is required.

**Team:** Mariana De La Cruz · Julian Motta

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The tests use an in-memory SQLite database and a fake clock, so they need no Docker, network, or wall-clock waits.

To run the same suite against PostgreSQL, point `GPU_TWIN_TEST_DATABASE_URL` at an empty database whose name ends in `_test`. The suite drops and recreates the schema for every test:

```bash
docker compose up -d db
docker compose exec db createdb -U twin gpu_lab_twin_test
GPU_TWIN_TEST_DATABASE_URL=postgresql+psycopg://twin:twin@localhost:5433/gpu_lab_twin_test pytest
```

### Browser E2E (Playwright) and load tests (k6)

Story 3.6 has a Playwright test that drives the real service. It needs Node.js 20+ and [uv](https://docs.astral.sh/uv/), because Playwright starts the API with `uv run`:

```bash
npm ci
npx playwright install chromium
npx playwright test                 # trace.zip is kept on retry; add --trace on to always keep one
npx playwright show-trace evidence/impl2/playwright/story-3.6-trace.zip
```

The fleet grid UI is served at http://localhost:8000/technician/fleet-grid.

Story 3.5's load script is `tests/nfr/telemetry-storm.js` and needs [k6](https://k6.io). On Windows, `scripts/run-story-3-5-nfr.ps1 -Profile smoke|adapted|full|ramp` starts an isolated service, runs k6, records peak memory, and writes logs to `evidence/impl2/nfr/`. On any OS: `K6_PROFILE=adapted BASE_URL=http://127.0.0.1:8000 k6 run tests/nfr/telemetry-storm.js`. CI runs the smoke and `adapted` profiles. The `adapted` profile is the formal Story 3.5 gate: 32 events/s for 60 s, p95 < 250 ms, p99 < 500 ms, zero failures, and RSS < 200 MB. The Annex `full` profile (2,000 events/s) is kept as documented RED evidence; see [walkthrough-impl2.md](walkthrough-impl2.md).

### Run the service with PostgreSQL

```bash
docker compose up --build
```

- API: http://localhost:8000 - interactive docs at http://localhost:8000/docs
- `GET /health` (liveness) and `GET /ready` (database reachable and the canonical 32-node fleet seeded)
- PostgreSQL is exposed on `localhost:5433` (user/password/db: `twin`/`twin`/`gpu_lab_twin`)

The container runs `alembic upgrade head`, then seeds the fleet from `fixtures/fleet.json` at startup.

### Run the service locally without Docker

```bash
alembic upgrade head          # creates gpu_lab_twin.db (SQLite) in the project root
uvicorn gpu_lab_twin.main:app --reload
```

Configuration is optional; see [.env.example](.env.example).

## Architecture

Reducer-centric **Ports & Adapters** (hexagonal), as specified in [planning/ARCHITECTURE.md](planning/ARCHITECTURE.md) and [ports-and-adapters.md](planning/detailed-design/ports-and-adapters.md).

```text
src/gpu_lab_twin/
├── domain/        pure model: states, fleet inventory, policies, explanations (no framework, DB, clock, or random)
├── ports/
│   ├── inbound/   use-case interfaces called by driving adapters
│   └── outbound/  Clock, NodeRepository — interfaces the core needs
├── application/   use-case services: validate, sequence, call the domain, commit through ports
├── adapters/
│   ├── db/        SQLAlchemy 2.0 models + repositories (PostgreSQL target, SQLite in tests)
│   ├── sim/       fleet fixture loader, FakeClock
│   └── clock/     SystemClock — the only wall-clock read
├── api/           FastAPI routes, DTOs, ErrorBody mapping
├── config/        environment settings (validated at startup)
└── bootstrap.py   composition root wiring adapters to ports
fixtures/fleet.json   canonical 32-node seed data
migrations/           Alembic migrations (mirror docs/contracts/schema.sql)
tests/                unit, integration and acceptance tests (pytest); e2e/ (Playwright + Page Objects); nfr/ (k6)
docs/                 PRD, active contracts, sprint-status.yaml, AI decision log
```

`tests/unit/test_architecture.py` enforces the dependency rule: `domain/`, `ports/` and `application/` never import FastAPI, Pydantic, SQLAlchemy, adapters, or the wall clock.

**Single-process prototype.** Heartbeat writes are serialized by one in-process lock that also assigns the global `ingest_offset` (AD-1). Run exactly one service process (`uvicorn` without `--workers`, one container). Revision compare-and-swap and unique indexes still reject a second writer rather than corrupting state, but a multi-process deployment would need a database-level sequencer. This matches the PRD's process-local baseline (NFR-12).

**Silent-node detection.** An in-process scan runs every `GPU_TWIN_LIVENESS_SCAN_SECONDS` (default 5 s; `0` disables it, and values must be ≥ 0.1 s). A node goes `OFFLINE` only once *strictly more* than 3 heartbeat intervals have passed since its last accepted heartbeat. With the 10 s fixture interval, that boundary is 30 s, and the scan period adds up to one period of latency, so OFFLINE appears between 30 s and 35 s after the last heartbeat.

Every error response uses the contract `ErrorBody` (`code`, `message`, `retryable`, `details`); no stack trace reaches a client.

## Project documents

| Document | Purpose |
|---|---|
| [docs/prd.md](docs/prd.md) | Module PRD (from Plan-2) |
| [docs/contracts/](docs/contracts/) | Active OpenAPI 3.1, SQL schema, behavioral contracts, events |
| [docs/sprint-status.yaml](docs/sprint-status.yaml) | BMad sprint tracking |
| [docs/ai-decision-log.md](docs/ai-decision-log.md) | Impl-1 AI prompts, outputs, and human review decisions |
| [walkthrough-impl1.md](walkthrough-impl1.md) | Impl-1 implementation walkthrough |
| [walkthrough-impl2.md](walkthrough-impl2.md) | Impl-2 walkthrough: stories 3.4–3.6, testing flows, k6 and Playwright results |
| [docs/ai-decision-log-impl2.md](docs/ai-decision-log-impl2.md) | Impl-2 AI decision log |
| [test/traceability-matrix.md](test/traceability-matrix.md) | Requirement → story → test → CI traceability and the Impl-2 quality gate |
| [evidence/impl2/](evidence/impl2/) | ATDD red/green logs, k6 results, Playwright run log and trace |
| `planning/`, `ux/`, `reviews/`, `test/` | Frozen Plan-2 / Solu-2 baseline (the `test/` RED contract suite is kept as Solu-2 evidence and is outside the default `pytest` run) |

## Scope

Owned by Module 3: fleet inventory, heartbeat ingestion, deterministic node state + cordon, silent-node detection, thermal cordon, and explanations. Reservations, scheduling, model catalog, inference, and enterprise observability belong to other modules and are not implemented here.
