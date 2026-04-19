# Acceptance Criteria

## 1. Correct Time Modeling

System must demonstrate:

- PPS used as anchor
- corrected_time ≠ arrival_time
- offset and drift modeled explicitly

---

## 2. State Machine Behavior

Must show:

- LOCKED achieved after PPS
- HOLDOVER entered when PPS missing
- LOST after extended absence
- relock after PPS recovery

---

## 3. Observability

System must output:

- offset trend
- drift trend
- jitter statistics
- confidence evolution
- state transitions

---

## 4. Demo Requirements

Must support:

``` text
python3 -m tools.run_demo --scenario <scenario>
```

Scenarios:

- normal
- holdover
- jitter_outlier

---

## 5. Metrics

System must compute:

- time_to_lock
- holdover_duration
- relock_pps_count
- residual statistics (p50/p95/max)
- jitter statistics
- confidence behavior

---

## 6. Robustness

System must handle:

- PPS outliers
- PPS loss
- clock drift
- non-monotonic timestamps

---

## 7. Output Artifacts

Each run must produce:

- corrected_events.jsonl
- summary.txt
- metrics.jsonl
- plots (offset/drift/confidence)

---

## 8. Engineering Quality

- modular code structure
- reproducible demo
- clear documentation
- deterministic mock data