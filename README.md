# GPU Lab Digital Twin

Module 3 of the **Academic AI Compute Fabric**.

## Team

- Mariana De La Cruz
- Julian Motta

## Module

**Module 3 — GPU Lab Digital Twin**  
**Tier:** Intermediate

This project defines a real-time digital twin for a university GPU laboratory composed of:

- 31 workstations with 1 × 24 GB GPU each
- 1 central server with 2 × 48 GB GPUs

The Digital Twin maintains the operational state of the fleet using simulated telemetry.

## Main Capabilities

The module tracks:

- GPU temperature
- VRAM occupancy
- driver health
- storage availability
- heartbeat freshness
- reservation context
- maintenance locks
- node operational state

## Mandatory Scenarios

1. **Fleet Heartbeat Ingestion**  
   Detect silent nodes after more than 3 missed heartbeat intervals.

2. **Thermal Anomaly & Automatic Cordon**  
   If `ws-gpu-14` exceeds 88°C, the node becomes `DEGRADED` and is cordoned from new jobs.

3. **Simulated Workstation Reboot**  
   If `ws-gpu-05` loses state after a reboot, it transitions to `RECOVERING`.

4. **Maintenance Drain**  
   The dual-GPU server performs a graceful workload drain before maintenance.

## Mandatory Edge Case

A node may alternate between online and offline every 5 seconds.

The system must prevent excessive state oscillation and alert flooding.

## Protagonists

- **Carlos** — Hardware Lab Technician
- **Alex** — Graduate Researcher

## Prototype

The planned standalone prototype is an:

**Interactive Fleet Map / Grid Dashboard with simulated telemetry injector and fault generator.**

Physical NVIDIA GPUs are not required.

This repository contains the planning and pre-implementation package. It does not claim that a production implementation exists.

## Current Status

- Phase 1 PRD: **COMPLETE**
- Phase 2 UX: **COMPLETE**
- Phase 3 Architecture: **COMPLETE**
- Phase 4 Readiness Gate: **COMPLETE**
- Final Readiness Status: **PASS**
- Blocking contradictions: **0**

## Project Structure

```text
planning/
├── prd.md
├── ARCHITECTURE.md
└── readiness-gate-report.md

ux/
├── DESIGN.md
├── EXPERIENCE.md
├── C-UX-Scenarios/
├── pages/
└── wireframes/

reviews/
├── review-prd-adversarial.md
├── review-ux-edge-cases.md
├── review-arch-adversarial.md
└── review-arch-edge-cases.md

ai-log/
└── decision-log.md
```
