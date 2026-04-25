# DSIL Time Engine Trial

This repository implements a host-side Time Engine prototype for DSIL SDK V1.

The goal is to transform raw `board_time_us` events into corrected timestamps using PPS as the timing anchor, while maintaining observability and system state.

---

## Key Features

- PPS-based time anchoring
- Offset and drift estimation
- Continuous timestamp correction
- HOLDOVER support when PPS is missing
- Synchronization state machine:
  - LOST
  - LOCKED
  - HOLDOVER
- Observability metrics for system behavior analysis

---

## Time Model

The engine models the mapping:

``` text
timestamp_corrected_us = board_time_us + predicted_offset_us
```

Where:

``` text
predicted_offset_us = offset_us + drift_ppm * dt
```

- `offset_us`: time bias between board clock and true time
- `drift_ppm`: rate of offset change (µs/s approximation)
- PPS provides absolute second-boundary constraints

Note:  
In this prototype, `drift_ppm` is modeled as offset rate (µs/s),  
not strict frequency ppm, which simplifies time-domain HOLDOVER.

---

## Scenarios

The demo includes three validation scenarios:

### 1. Normal

- Stable PPS
- Normal jitter
- Expected behavior:
  - Fast lock
  - Stable offset/drift
  - High confidence

---

### 2. Holdover

- PPS loss between 6s–9s
- Expected behavior:
  - LOCKED → HOLDOVER → LOCKED
  - Continuous timestamp output
  - Confidence drops and recovers

---

### 3. PPS Outlier

- Inject abnormal PPS at t=5s (+5000us)
- Expected behavior:
  - No false lock
  - No large offset jump
  - System remains stable

---

## Run Demo

```bash
PYTHONPATH=. python3 tools/run_demo.py --scenario normal

Other scenarios:

PYTHONPATH=. python3 tools/run_demo.py --scenario holdover
PYTHONPATH=. python3 tools/run_demo.py --scenario jitter_outlier
PYTHONPATH=. python3 tools/run_demo.py --scenario drift_jump
```

## Outputs

Each run generates:

``` text
outputs/<scenario>/
├── corrected_events.jsonl
└── summary.txt
```

---

## Observability Metrics

The system exposes the following metrics:

### Synchronization

- Time to LOCKED  
- HOLDOVER duration  
- Relock PPS count  

### Accuracy

- Residual (p50 / p95 / max)  
- PPS jitter (p50 / p95 / max)  

### Confidence

- Minimum confidence  
- Recovery time after degradation  

---

## Example Summary

``` text
Scenario: normal
Total events: 1572
Final state: LOCKED
Final offset_us: 3382.61
Final drift_ppm: -9.95
Final confidence: 0.946

=== Observability Metrics ===
Time to LOCKED: N/A
Holdover duration: 5.00 s
Relock PPS count: 0

Residual stats (us):
  p50: 31.00
  p95: 68.19
  max: 68.19

Jitter stats (us):
  p50: 10.00
  p95: 45.00
  max: 45.00

Confidence:
  min: 0.000
  recovery_time: 2.99653

Offset continuity (us):
  max_jump: 3494.00
  p95: 0.13

Holdover drift growth: 67.71 us

Confidence behavior:
  degraded during holdover: True
  recovered after relock: True

State transitions:
  -3633 us -> LOST
  2996530 us -> LOCKED
  5996567 us -> HOLDOVER
  10996642 us -> LOCKED
```

---

## Design Principles

- `board_time_us` is the only authoritative time axis  
- PPS is the only timing anchor  
- arrival time is not used  
- corrected timestamp is the only output  
- system behavior must be observable and explainable  

---

## Repository Structure

``` text
engine/ # time engine core
tools/ # demo and utilities
outputs/ # generated results (not committed)
```

---

## Notes

This is a prototype implementation focused on:

- clarity  
- observability  
- correctness of time modeling  

rather than production-level precision.
