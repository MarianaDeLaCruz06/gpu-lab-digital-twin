import { expect, type Page } from '@playwright/test';

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
    await this.cards.filter({ hasText: 'server-gpu-01' }).click();
    await expect(this.page.getByTestId('selected-label')).toHaveText('server-gpu-01');
    await expect(this.page.getByTestId('canonical-id')).toHaveText('central-gpu-server');
  }

  async expectState(state: string) { await expect(this.selectedState).toHaveText(state); }
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
}
