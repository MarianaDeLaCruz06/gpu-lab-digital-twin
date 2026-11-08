import { randomUUID } from 'node:crypto';

export function healthyServerHeartbeat() {
  const now = new Date().toISOString();
  return {
    eventId: randomUUID(), occurredAt: now, receivedAt: now, schemaVersion: '1.0',
    bootSessionId: `e2e-${randomUUID()}`, previousBootSessionId: null, stateLoss: false,
    sourceSequence: 1,
    gpuSamples: [
      { gpuDeviceId: 'central-gpu-server-gpu-0', temperatureC: 45, vramOccupiedGb: 0 },
      { gpuDeviceId: 'central-gpu-server-gpu-1', temperatureC: 46, vramOccupiedGb: 0 },
    ],
    driverHealth: 'HEALTHY', storageFreeGb: 3000, externalContext: null,
  };
}
