import { randomUUID } from 'node:crypto';

import { expect, type Page } from '@playwright/test';

// Story 3.6 badge colors: Green -> Amber -> Blue, as rendered by fleet-map.css.
const BADGE = {
  HEALTHY: { tone: 'green', background: 'rgb(30, 123, 79)' },
  DRAINING: { tone: 'amber', background: 'rgb(255, 189, 102)' },
  MAINTENANCE: { tone: 'blue', background: 'rgb(47, 111, 208)' },
} as const;
type BadgeState = keyof typeof BADGE;

export class FleetMapPage {
  constructor(private readonly page: Page) {}

  private get cards() { return this.page.getByTestId('node-card'); }
  private get selectedState() { return this.page.getByTestId('selected-state'); }
  private get selectedEligibility() { return this.page.getByTestId('selected-eligibility'); }
  private get startDrainButton() { return this.page.getByTestId('start-drain'); }
  private get completeJobsButton() { return this.page.getByTestId('complete-jobs'); }
  private get message() { return this.page.getByTestId('maintenance-message'); }
  private get error() { return this.page.getByTestId('maintenance-error'); }
  private get reason() { return this.page.getByLabel('Maintenance reason'); }

  async open() {
    const fleet = this.page.waitForResponse(response => response.url().endsWith('/v1/nodes') && response.ok());
    await this.page.goto('/technician/fleet-grid');
    await fleet;
    await expect(this.page.getByRole('heading', { name: 'Fleet Grid' })).toBeVisible();
  }

  async expectFleetSize(count: number) { await expect(this.cards).toHaveCount(count); }

  async selectServer() {
    await this.serverCard.click();
    await expect(this.page.getByTestId('selected-label')).toHaveText('server-gpu-01');
    await expect(this.page.getByTestId('canonical-id')).toHaveText('central-gpu-server');
  }

  private get serverCard() { return this.cards.filter({ hasText: 'server-gpu-01' }); }

  async expectState(state: BadgeState) {
    const { tone, background } = BADGE[state];
    await expect(this.selectedState).toHaveText(state);
    await expect(this.selectedState).toHaveAttribute('data-tone', tone);
    await expect(this.selectedState).toHaveCSS('background-color', background);
    const cardBadge = this.serverCard.getByTestId('node-state');
    await expect(cardBadge).toHaveText(state);
    await expect(cardBadge).toHaveAttribute('data-tone', tone);
  }
  async expectEligibility(text: string) { await expect(this.selectedEligibility).toHaveText(text); }

  async startDrain() {
    const response = this.page.waitForResponse(value => value.url().includes('/maintenance-drains'));
    await this.startDrainButton.click();
    expect((await response).status()).toBe(201);
    await expect(this.message).toHaveText('Maintenance drain started.');
  }

  async retryDrain() {
    const response = this.page.waitForResponse(value => value.url().includes('/maintenance-drains'));
    await this.startDrainButton.click();
    expect((await response).status()).toBe(200);
    await expect(this.message).toHaveText('Existing maintenance drain reused.');
  }

  async submitConflictingDrain() {
    await this.reason.fill('Changed maintenance reason');
    const response = this.page.waitForResponse(value => value.url().includes('/maintenance-drains'));
    await this.startDrainButton.click();
    expect((await response).status()).toBe(409);
    await expect(this.error).toContainText('ERR_IDEMPOTENCY_CONFLICT');
  }

  async completeSimulatedJobs() {
    const response = this.page.waitForResponse(value => value.url().includes('/workload-snapshots'));
    await this.completeJobsButton.click();
    expect((await response).status()).toBe(200);
    await expect(this.message).toHaveText('Simulated active jobs completed.');
  }

  /** Module 3 owns no job dispatcher, so new work is modelled as a fresh maintenance request plus the fleet's cordon flag. */
  async expectNewWorkRefused() {
    const fleet = await this.page.request.get('/v1/nodes');
    expect(fleet.ok()).toBeTruthy();
    const server = (await fleet.json()).nodes.find((node: { nodeId: string }) => node.nodeId === 'central-gpu-server');
    expect(server.cordoned).toBe(true);
    const now = new Date().toISOString();
    const response = await this.page.request.post('/v1/nodes/central-gpu-server/maintenance-drains', {
      data: {
        eventId: randomUUID(), requestId: randomUUID(), occurredAt: now, schemaVersion: '1.0',
        startsAt: now, reason: 'Second technician request', expectedNodeRevision: server.nodeRevision, actor: 'Carlos',
      },
    });
    expect(response.status()).toBe(409);
    expect((await response.json()).code).toBe('ERR_MAINTENANCE_CONFLICT');
  }
}
