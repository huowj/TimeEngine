# Architecture

## 1. Overview

This repository implements a host-side Time Engine for DSIL SDK V1.

The system processes timing and sensor packets defined in `board_time_us`, uses PPS as the only timing anchor, and produces:

- corrected timestamps
- synchronization state
- observability metrics

---

## 2. System Boundary (Fixed)

The architecture follows strict separation:

| Component | Responsibility |
|----------|----------------|
| Firmware | Generates packets |
| Time Engine | Time correction rules (THIS PROJECT) |
| Host | Applies corrected timestamps |
| ROS2 | Visualization |

This implementation ONLY covers:

- Time Engine logic on host side

---

## 3. Data Flow

``` text
Mock Events → TimeEngine → Corrected Events + Metrics
```

Detailed:

``` text
generate_events()
↓
Packet stream (jsonl)
↓
TimeEngine.process_packet()
↓
CorrectedEvent + internal state
↓
metrics / plots / summary
```

---

## 4. Module Responsibilities

### engine/models.py

Defines:

- `Packet`
- `CorrectedEvent`
- `SyncState`

---

### engine/engine.py

Core logic:

- PPS anchor alignment
- offset estimation
- drift tracking
- HOLDOVER logic
- state machine
- confidence estimation

---

### tools/run_demo.py

Orchestration:

- mock data generation
- engine execution
- metrics collection
- summary output
- visualization

---

### tools/metrics_utils.py

Computes observability metrics:

- time to lock
- holdover duration
- relock PPS count
- residual / jitter statistics
- confidence behavior

---

### tools/plot_metrics.py

Visualization:

- offset trend
- drift trend
- confidence trend

---

## 5. State Machine

States:

- `LOST`: no reliable PPS
- `LOCKED`: PPS stable
- `HOLDOVER`: PPS missing, predicting

Transitions:

``` text
LOST → LOCKED (after stable PPS)
LOCKED → HOLDOVER (PPS missing)
HOLDOVER → LOST (timeout)
HOLDOVER → LOCKED (PPS recovered)
```

---

## 6. Design Principles

1. PPS is the only timing anchor
2. board_time_us is immutable input
3. corrected timestamp is the only output
4. system must remain observable
5. HOLDOVER must degrade gracefully

---

## 7. Non-Goals

This project does NOT include:

- firmware changes
- protocol design
- ROS2 integration
- transport layer
