# GPU Lab Digital Twin

Module 3 of the **Academic AI Compute Fabric** — a standalone, hardware-agnostic digital twin of the university GPU lab: 31 workstations with one 24 GB GPU each and one server with two 48 GB GPUs (32 nodes, 33 GPUs, 840 GB VRAM). All telemetry is simulated; no NVIDIA hardware, CUDA, or other team's module is required.

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

### Run the service with PostgreSQL

```bash
docker compose up --build
```

- API: http://localhost:8000 — interactive docs at http://localhost:8000/docs
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
tests/                unit + integration tests (pytest)
docs/                 PRD, active contracts, sprint-status.yaml, AI decision log
```

`tests/unit/test_architecture.py` enforces the dependency rule: `domain/`, `ports/` and `application/` never import FastAPI, Pydantic, SQLAlchemy, adapters, or the wall clock.

Every error response uses the contract `ErrorBody` (`code`, `message`, `retryable`, `details`); no stack trace reaches a client.

## Project documents

| Document | Purpose |
|---|---|
| [docs/prd.md](docs/prd.md) | Module PRD (from Plan-2) |
| [docs/contracts/](docs/contracts/) | Active OpenAPI 3.1, SQL schema, behavioral contracts, events |
| [docs/sprint-status.yaml](docs/sprint-status.yaml) | BMad sprint tracking |
| [docs/ai-decision-log.md](docs/ai-decision-log.md) | Impl-1 AI prompts, outputs, and human review decisions |
| [walkthrough-impl1.md](walkthrough-impl1.md) | Impl-1 implementation walkthrough |
| `planning/`, `ux/`, `reviews/`, `test/` | Frozen Plan-2 / Solu-2 baseline (the `test/` RED contract suite is kept as Solu-2 evidence and is outside the default `pytest` run) |

## Scope

Owned by Module 3: fleet inventory, heartbeat ingestion, deterministic node state + cordon, silent-node detection, thermal cordon, and explanations. Reservations, scheduling, model catalog, inference, and enterprise observability belong to other modules and are not implemented here.
