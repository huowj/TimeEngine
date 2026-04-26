# Acceptance Criteria

## 1. Correct Time Modeling

System must demonstrate:

- PPS is used as the only timing anchor.
- `timestamp_corrected_us` is computed from:

``` text
timestamp_corrected_us = board_time_us + predicted_offset_us
```

- `timestamp_corrected_us` must not depend on packet arrival time.
- Offset and drift must be modeled explicitly.

### Acceptance Boundary

| Metric                                | Requirement                            |
| ------------------------------------- | -------------------------------------- |
| final offset error in normal scenario | stable, no unbounded growth            |
| final drift estimate                  | non-zero when board clock drift exists |
| corrected timestamp monotonicity      | 100% monotonic after correction        |
| arrival time usage                    | not used as truth source               |

---

## 2. State Machine Behavior

System must show:

- `LOCKED` achieved after PPS
- `HOLDOVER` entered when PPS missing
- `LOST` after extended absence
- Relock after PPS recovery.

### Acceptance Boundary

| Scenario | Requirement |
|---|---|
| normal | reaches `LOCKED` |
| holdover | enters `HOLDOVER` after PPS gap > 1.5s |
| holdover | enters `LOST` if PPS gap > 5s |
| holdover recovery | returns to `LOCKED` after stable PPS resumes |
| jitter_outlier | rejects bad PPS and does not corrupt offset/drift or lock state |
| drift_jump | confidence drops and model re-converges |

---

## 3. Observability

System must output:

- offset trend
- drift trend
- jitter statistics
- confidence evolution
- state transitions

### Acceptance Boundary

Each demo run must produce observable values for:

| Artifact | Required Content |
|---|---|
| metrics.jsonl | offset, drift, confidence, residual, jitter, state |
| summary.txt | final state, final offset, final drift, final confidence |
| plots | offset trend, drift trend, confidence trend |
| state transitions | timestamp + state name |

---

## 4. Demo Requirements

Must support:

``` text
PYTHONPATH=. python3 tools/run_demo.py --scenario <scenario>
```

Scenarios:

- normal
- holdover
- jitter_outlier
- drift_jump

### Acceptance Boundary

| Scenario | Expected Behavior |
|---|---|
| normal | locks and remains stable |
| holdover | enters HOLDOVER during PPS loss |
| jitter_outlier | rejects PPS outlier |
| drift_jump | detects degraded timing quality and re-converges |

---

## 5. Metrics

System must compute:

- time_to_lock
- holdover_duration
- relock_pps_count
- residual statistics (p50/p95/max)
- jitter statistics
- confidence behavior

### Acceptance Boundary

| Metric | Scenario | Requirement |
|---|---|---|
| time_to_lock | normal | < 4.0 s |
| holdover_duration | holdover | >= 3.0 s |
| relock_pps_count | holdover | <= 4 PPS |
| residual p95 | normal | < 500 us |
| residual max | normal | < 1000 us |
| jitter p95 | normal | < 300 us |
| confidence min | normal | >= 0.6 after LOCKED |
| confidence degradation | holdover | decreases during PPS loss |
| confidence recovery | relock | increases after stable PPS resumes within <= 4 PPS |
| offset continuity max jump | normal | < 1000 us |
| holdover drift growth | holdover | bounded, no unbounded growth |

---

## 6. Robustness

System must handle:

- PPS outliers
- PPS loss
- clock drift
- drift jump / clock change
- non-monotonic timestamps

### Acceptance Boundary

| Condition | Requirement |
|---|---|
| PPS outlier | must not corrupt offset/drift estimate |
| PPS outlier | must not cause false LOCKED |
| PPS loss | must enter HOLDOVER |
| long PPS loss | must enter LOST |
| PPS recovery | must relock after stable PPS |
| large jitter | must prevent LOCKED |
| drift jump | confidence must decrease temporarily |
| drift jump | offset/drift must re-converge |
| non-monotonic board time | corrected timestamp remains monotonic |

## 7. Output Artifacts

### Acceptance Boundary

| File | Requirement |
|---|---|
| corrected_events.jsonl | one corrected event per input event |
| metrics.jsonl | one metrics row per processed event |
| summary.txt | includes all required metrics |
| plots | includes offset, drift, confidence trends |

---

## 8. Engineering Quality

System must demonstrate:

- modular code structure
- reproducible demo
- deterministic mock data
- clear documentation
- test coverage for key timing behavior

### Acceptance Boundary

Required tests:

- LOCKED should not occur under large jitter
- confidence decreases during HOLDOVER
- confidence recovers after relock
- offset/drift re-converges after drift change
- corrected timestamps remain monotonic
- PPS outliers are rejected

All tests must pass with:

``` text
pytest
```

---

## 9. Final Acceptance Summary

A run is considered accepted if:

1. All required scenarios run successfully.
2. All required artifacts are generated.
3. All required metrics are present.
4. Metrics satisfy the acceptance boundaries.
5. State transitions match expected behavior.
6. pytest passes.
