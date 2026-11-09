import { defineConfig, devices } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import path from 'node:path';

const baseURL = process.env.BASE_URL ?? 'http://127.0.0.1:8765';
const runId = process.env.PLAYWRIGHT_RUN_ID ?? `${process.pid}-${Date.now()}`;
const databasePath = path.resolve(`test-results/playwright-e2e-${runId}.db`);
// SQLite cannot create the database file when its folder is missing (fresh clone or CI).
mkdirSync(path.dirname(databasePath), { recursive: true });

export default defineConfig({
  testDir: './tests/e2e',
  outputDir: './test-results/playwright',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 1,
  forbidOnly: !!process.env.CI,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['junit', { outputFile: 'test-results/playwright-results.xml' }],
  ],
  use: {
    baseURL,
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'uv run alembic upgrade head && uv run uvicorn gpu_lab_twin.main:app --host 127.0.0.1 --port 8765',
    url: `${baseURL}/ready`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      ...process.env,
      GPU_TWIN_DATABASE_URL: `sqlite+pysqlite:///${databasePath.replaceAll('\\', '/')}`,
      GPU_TWIN_LIVENESS_SCAN_SECONDS: '0',
      GPU_TWIN_POLICY_VERSION: 'impl2-e2e-v1',
    },
  },
});
