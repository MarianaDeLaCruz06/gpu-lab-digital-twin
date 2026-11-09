import crypto from 'k6/crypto';
import http from 'k6/http';
import { check } from 'k6';
import { Counter, Rate } from 'k6/metrics';

const baseUrl = __ENV.BASE_URL || 'http://127.0.0.1:8766';
const profile = (__ENV.K6_PROFILE || 'smoke').toLowerCase();
const serverErrors = new Rate('unhandled_server_error_rate');
const acceptedResponses = new Counter('canonical_responses');

const nodes = Array.from({ length: 31 }, (_, index) => `ws-gpu-${String(index + 1).padStart(2, '0')}`)
  .concat('central-gpu-server');

const fullScenario = {
  executor: 'constant-arrival-rate',
  rate: 2000,
  timeUnit: '1s',
  duration: '60s',
  preAllocatedVUs: 256,
  maxVUs: 2000,
};
// Story 3.5 adapted formal gate (I2-DL-15): 32 nodes x 1 heartbeat/s for 60 s, i.e. 10x the
// fleet's configured 0.1 Hz heartbeat load, every event durably committed before its ack (AD-1).
// The Annex 2,000 events/s figure stays available as the `full` profile and is kept as RED evidence.
const adaptedScenario = {
  executor: 'constant-arrival-rate',
  rate: 32,
  timeUnit: '1s',
  duration: '60s',
  preAllocatedVUs: 16,
  maxVUs: 64,
};
const smokeScenario = {
  executor: 'constant-arrival-rate',
  rate: 5,
  timeUnit: '1s',
  duration: '5s',
  preAllocatedVUs: 8,
  maxVUs: 32,
};
function rampScenario() {
  const rate = Number(__ENV.RAMP_RATE || __ENV.K6_RATE || '100');
  const duration = __ENV.RAMP_DURATION || '10s';
  const maxVUs = Number(__ENV.RAMP_MAX_VUS || String(Math.max(64, Math.ceil(rate * 2))));
  return {
    executor: 'constant-arrival-rate',
    rate,
    timeUnit: '1s',
    duration,
    preAllocatedVUs: Math.min(maxVUs, Math.max(32, Math.ceil(rate / 2))),
    maxVUs,
  };
}
const isRamp = profile === 'ramp' || Boolean(__ENV.RAMP_RATE || __ENV.K6_RATE);
const namedScenarios = { full: fullScenario, adapted: adaptedScenario, smoke: smokeScenario };
const scenario = isRamp ? rampScenario() : (namedScenarios[profile] || smokeScenario);
const isAdapted = profile === 'adapted' && !isRamp;
if (isAdapted) {
  // A typed 409 ordering conflict is a canonical, handled answer; anything else counts as a failed request.
  http.setResponseCallback(http.expectedStatuses(200, 409));
}

export const options = {
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
  scenarios: { telemetry_storm: scenario },
  thresholds: {
    unhandled_server_error_rate: ['rate==0'],
    ...(isRamp || isAdapted ? {} : { http_req_duration: ['p(95)<5000'] }),
    ...(profile === 'full' && !isRamp ? { dropped_iterations: ['count==0'] } : {}),
    ...(isAdapted
      ? {
          http_req_duration: ['p(95)<250', 'p(99)<500'],
          http_req_failed: ['rate==0'],
          checks: ['rate==1'],
          dropped_iterations: ['count==0'],
        }
      : {}),
  },
};

function bodyFor(nodeId) {
  const now = new Date().toISOString();
  const digest = crypto.md5(`${now}:${nodeId}:${__VU}:${__ITER}`, 'hex');
  const eventId = `${digest.slice(0, 8)}-${digest.slice(8, 12)}-4${digest.slice(13, 16)}-a${digest.slice(17, 20)}-${digest.slice(20, 32)}`;
  const gpuIds = nodeId === 'central-gpu-server'
    ? ['central-gpu-server-gpu-0', 'central-gpu-server-gpu-1']
    : [`${nodeId}-gpu-0`];
  return JSON.stringify({
    eventId,
    occurredAt: now,
    receivedAt: now,
    schemaVersion: '1.0',
    bootSessionId: 'k6-storm-boot',
    previousBootSessionId: null,
    stateLoss: false,
    sourceSequence: null,
    gpuSamples: gpuIds.map((gpuDeviceId, index) => ({
      gpuDeviceId,
      temperatureC: 40 + ((__ITER + index) % 45),
      vramOccupiedGb: (__ITER + index) % 20,
    })),
    driverHealth: 'HEALTHY',
    storageFreeGb: 320,
    externalContext: null,
  });
}

export default function () {
  const nodeId = nodes[(__VU + __ITER) % nodes.length];
  const response = http.post(`${baseUrl}/v1/nodes/${nodeId}/heartbeats`, bodyFor(nodeId), {
    headers: { 'Content-Type': 'application/json' },
    tags: { profile, route: 'canonical-heartbeat' },
  });
  const isServerError = response.status >= 500;
  serverErrors.add(isServerError);
  if (response.status === 200 || response.status === 409) acceptedResponses.add(1);
  check(response, {
    'no unhandled 5xx': () => !isServerError,
    'canonical response or typed ordering conflict': value => value.status === 200 || value.status === 409,
  });
}
