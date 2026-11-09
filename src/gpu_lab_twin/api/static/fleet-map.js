const grid = document.querySelector('[data-testid="fleet-grid"]');
const detail = document.querySelector('[data-testid="node-detail"]');
const stateEl = document.querySelector('[data-testid="selected-state"]');
const eligibilityEl = document.querySelector('[data-testid="selected-eligibility"]');
const errorEl = document.querySelector('[data-testid="maintenance-error"]');
const messageEl = document.querySelector('[data-testid="maintenance-message"]');
const drainButton = document.querySelector('[data-testid="start-drain"]');
const completeButton = document.querySelector('[data-testid="complete-jobs"]');
let selected;
let maintenanceRequest;

const alias = node => node.nodeId === 'central-gpu-server' ? 'server-gpu-01' : node.nodeId;
const eligibility = node => node.cordoned ? 'Unavailable for new work' : 'Eligible for new work';
// Story 3.6 badge colors: Green (HEALTHY) -> Amber (DRAINING) -> Blue (MAINTENANCE).
const TONES = { HEALTHY: 'green', DRAINING: 'amber', MAINTENANCE: 'blue', DEGRADED: 'red', OFFLINE: 'red' };
const tone = state => TONES[state] ?? 'neutral';

async function loadFleet() {
  const response = await fetch('/v1/nodes');
  if (!response.ok) throw new Error('Fleet could not be loaded.');
  const fleet = await response.json();
  grid.replaceChildren(...fleet.nodes.map(node => {
    const card = document.createElement('button');
    card.className = 'node';
    card.dataset.testid = 'node-card';
    card.dataset.nodeId = node.nodeId;
    card.innerHTML = `<strong>${alias(node)}</strong><span>${node.kind}</span><span class="state" data-testid="node-state" data-tone="${tone(node.state)}">${node.state}</span><span>${eligibility(node)}</span>`;
    card.addEventListener('click', () => selectNode(node));
    return card;
  }));
  if (selected) {
    const current = fleet.nodes.find(node => node.nodeId === selected.nodeId);
    if (current) selectNode(current, false);
  }
}

function selectNode(node, reset = true) {
  selected = node;
  detail.hidden = false;
  document.querySelector('[data-testid="selected-label"]').textContent = alias(node);
  document.querySelector('[data-testid="canonical-id"]').textContent = node.nodeId;
  stateEl.textContent = node.state;
  stateEl.dataset.tone = tone(node.state);
  eligibilityEl.textContent = eligibility(node);
  completeButton.hidden = node.state !== 'DRAINING';
  drainButton.textContent = maintenanceRequest && !reset ? 'Retry maintenance drain' : 'Start maintenance drain';
  if (reset) { errorEl.hidden = true; messageEl.textContent = ''; }
}

async function startDrain() {
  errorEl.hidden = true;
  const now = new Date().toISOString();
  if (!maintenanceRequest) {
    maintenanceRequest = {
      eventId: crypto.randomUUID(), requestId: crypto.randomUUID(), occurredAt: now, schemaVersion: '1.0',
      startsAt: now, reason: document.querySelector('#reason').value,
      expectedNodeRevision: selected.nodeRevision, actor: 'Carlos'
    };
  } else {
    maintenanceRequest.reason = document.querySelector('#reason').value;
  }
  const response = await fetch(`/v1/nodes/${selected.nodeId}/maintenance-drains`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(maintenanceRequest)
  });
  const body = await response.json();
  if (!response.ok) {
    errorEl.textContent = `${body.code}: ${body.message}`;
    errorEl.hidden = false;
    return;
  }
  messageEl.textContent = body.outcome === 'DUPLICATE'
    ? 'Existing maintenance drain reused.' : 'Maintenance drain started.';
  drainButton.textContent = 'Retry maintenance drain';
  await loadFleet();
}

async function completeJobs() {
  const now = new Date().toISOString();
  const body = {
    eventId: crypto.randomUUID(), snapshotId: crypto.randomUUID(), nodeId: selected.nodeId,
    source: 'EXTERNAL_MOCK', sourceRevision: Date.now(), observedAt: now, receivedAt: now,
    activeWorkloadCount: 0, activeWorkloadIds: []
  };
  const response = await fetch('/v1/fixtures/workload-snapshots', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
  });
  const result = await response.json();
  if (!response.ok) {
    errorEl.textContent = `${result.code}: ${result.message}`;
    errorEl.hidden = false;
    return;
  }
  messageEl.textContent = 'Simulated active jobs completed.';
  await loadFleet();
}

drainButton.addEventListener('click', startDrain);
completeButton.addEventListener('click', completeJobs);
document.querySelector('#close-detail').addEventListener('click', () => { detail.hidden = true; });
loadFleet().catch(error => {
  errorEl.textContent = error.message;
  errorEl.hidden = false;
  detail.hidden = false;
});
