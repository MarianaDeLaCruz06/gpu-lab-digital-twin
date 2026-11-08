import { expect, test } from '@playwright/test';

import { FleetMapPage } from './pages/FleetMapPage';
import { healthyServerHeartbeat } from './support/heartbeat-factory';

test('Carlos drains server-gpu-01 without duplicate locks and sees maintenance', async ({ page, request }) => {
  await test.step('Given the canonical server is healthy and eligible', async () => {
    const response = await request.post('/v1/nodes/central-gpu-server/heartbeats', {
      data: healthyServerHeartbeat(),
    });
    expect(response.ok()).toBeTruthy();
  });

  const fleet = new FleetMapPage(page);
  await test.step('Carlos opens the real 32-node fleet grid', async () => {
    await fleet.open();
    await fleet.expectFleetSize(32);
    await fleet.selectServer();
    await fleet.expectState('HEALTHY');
    await fleet.expectEligibility('Eligible for new work');
  });

  await test.step('He starts maintenance and immediately sees draining and cordon', async () => {
    await fleet.startDrain();
    await fleet.expectState('DRAINING');
    await fleet.expectEligibility('Unavailable for new work');
  });

  await test.step('An identical request reuses the same maintenance operation', async () => {
    await fleet.retryDrain();
    await fleet.expectState('DRAINING');
  });

  await test.step('A changed replay shows the canonical typed conflict', async () => {
    await fleet.submitConflictingDrain();
  });

  await test.step('Fresh simulated workload completion moves the server to maintenance', async () => {
    await fleet.completeSimulatedJobs();
    await fleet.expectState('MAINTENANCE');
    await fleet.expectEligibility('Unavailable for new work');
  });
});
