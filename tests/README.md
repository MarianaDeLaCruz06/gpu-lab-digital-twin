# Test architecture

## Setup

Install Python development dependencies with `uv sync --extra dev`. Install browser tooling with `npm install`, then install the pinned Playwright browser using `npx playwright install chromium`.

The suite starts a real FastAPI process and a fresh SQLite database for every Playwright invocation. No page route or API response is mocked.

## Commands

- `uv run pytest` — backend unit, integration, and acceptance tests.
- `uv run pytest --cov=gpu_lab_twin --cov-branch` — line and branch coverage.
- `npm run test:e2e` — headless Chromium E2E suite.
- `npm run test:e2e:headed` — headed local browser run.
- `npm run test:e2e:debug` — Playwright inspector.

## Layout

- `unit/` contains pure policy and reducer tests.
- `integration/` exercises adapters and HTTP contracts against a real test database.
- `acceptance/` contains Story 3.4 ATDD behavior.
- `nfr/` contains k6 scripts that exercise the running API.
- `e2e/pages/FleetMapPage.ts` owns every fleet-page selector and browser interaction.
- `e2e/support/` contains pure data factories used for API-first setup.

## Practices

Use stable roles, labels, and `data-testid` locators through Page Objects. Register response waits before actions, prefer web-first assertions, and never use `waitForTimeout`, `time.sleep`, or arbitrary fixed delays. Each backend test uses isolated fixtures; Playwright uses a unique database file per invocation. Preserve screenshots/videos on failure and `trace.zip` on the first retry.

The scaffold follows the TEA fixture-architecture, data-factory, network-first, Playwright-config, and test-quality guidance. Codex has no write-time tool-hook interception, so enforcement remains Ruff, repository searches, and the TEA test-review workflow. k6 scripts are reviewed separately because k6 may legitimately model arrival rates, although this project uses no scripted sleep.
