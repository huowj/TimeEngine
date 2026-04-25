# Time Model

## 1. Scope

This document defines the host-side time model for the DSIL SDK V1 Time Engine trial.

The Time Engine is responsible for:

- using PPS as the timing anchor
- estimating offset and drift on top of `board_time_us`
- producing corrected timestamps for sensor events
- maintaining confidence and synchronization state
- supporting holdover when PPS is temporarily missing

The Time Engine does not modify firmware, packet format, transport, or ROS2 integration.

---

## 2. Invariants

### 2.1 Authoritative time axis

`board_time_us` is the only authoritative time value carried by incoming packets.

All input events are defined on the `board_time_us` axis.

---

### 2.2 Anchor semantics

PPS is the only timing anchor.

PPS does not introduce a new free-running time source.  
Instead, PPS provides a recurring absolute second-boundary constraint that allows the Time Engine to estimate the mapping from `board_time_us` to corrected time.

---

### 2.3 Output semantics

Arrival time is not truth.

The only time value exported by the Time Engine is:

- `timestamp_corrected_us`

---

## 3. Event Types

```json
{
  "type": "TIMING_EVENT | SENSOR_EVENT",
  "sensor_id": "imu_vn100_0",
  "board_time_us": 1000234,
  "payload": {}
}
```

---

## 4. Core Time Mapping

The Time Engine models a mapping:

``` text
timestamp_corrected_us = board_time_us + predicted_offset_us
```

Where `predicted_offset_us` is dynamically estimated.

---

## 5. Offset Model

### 5.1 measured_offset_us

#### Definition

`measured_offset_us` is the instantaneous offset between the expected true time (from PPS) and the observed `board_time_us`.

#### Formula

``` text
target_time_us = n * 1_000_000
measured_offset_us = target_time_us - board_time_us
```

#### Explanation

- `target_time_us`: expected true time (absolute second boundary)

- `board_time_us`: observed timestamp

- `measured_offset_us`: raw offset measurement

### 5.2 offset_us (filtered)

To reduce noise, offset is filtered using exponential moving average:

``` text
offset_us = α * measured_offset_us + (1 - α) * offset_us
```

Where:

- `α ∈ [0.2, 0.4]`

---

### 5.3 predicted_offset_us

#### Definition

`predicted_offset_us` is the forward-estimated offset used for correcting non-PPS events.

#### Formula

``` text
predicted_offset_us = offset_us + drift_ppm * dt_s
```

Where:

``` text
dt_s = (current_board_time - last_pps_board_time) / 1e6
```

---

## 6. Drift Model

### 6.1 Definition of drift_ppm

``` text
drift_ppm ≈ d(offset_us) / dt
```

That is:

- drift_ppm represents the rate of change of offset (µs per second)

---

### 6.2 Clarification vs real ppm

Strict definition:

``` text
ppm = (Δf / f) * 1e6
```

In this system:

``` text
1 ppm ≈ 1 µs / second
```

Conclusion:

- This is NOT strict frequency ppm
- It is an engineering approximation

---

### 6.3 Drift estimation

``` text
measured_drift = (measured_offset_k - measured_offset_{k-1}) / dt_s
```

Smoothed as:

``` text
drift_ppm = β * measured_drift + (1 - β) * drift_ppm
```

Where:

- `β ∈ [0.1, 0.3]`

---

## 7. Holdover Model

When PPS is missing:

``` text
predicted_offset_us = offset_us + drift_ppm * dt_s
```

Corrected timestamp:

``` text
timestamp_corrected_us = board_time_us + predicted_offset_us
```

---

## 8. Sync State Machine

### 8.1 States

- LOST
- LOCKED
- HOLDOVER

---

### 8.2 LOCKED

#### Enter conditions

1. consecutive_good_pps ≥ 3
2. |residual_us| < threshold
3. PPS interval jitter is small:
   |interval_us - 1_000_000| < jitter_threshold
4. drift is stable:
   max(drift over last N samples) - min(...) < drift_stability_threshold

#### Why needed

Residual alone is insufficient for lock detection.

Without jitter and drift constraints, the system may falsely enter LOCKED
under unstable PPS or transient conditions.

#### Exit condition

``` text
PPS gap > holdover_timeout → HOLDOVER
```

---

### 8.3 HOLDOVER

#### Enter condition

``` text
PPS missing > holdover_timeout (≈1.5s)
```

#### Behavior

- continue prediction using offset + drift
- no new measurements

#### Exit conditions

``` text
PPS resumes and stabilizes → LOCKED
PPS missing > lost_timeout (≈5s) → LOST
```

---

### 8.4 LOST

#### Enter conditions

1. No PPS received yet
2. PPS missing > lost_timeout
3. Confidence too low

#### Exit condition

``` text
Receive stable PPS → LOCKED
```

---

## 9. Residual Definition

``` text
residual_us = measured_offset_us - predicted_offset_us
```

Where:

- residual_us is the prediction error of the time model

---

## 10. Jitter Definition

``` text
interval_us = current_pps_time - previous_pps_time
jitter_us = interval_us - 1_000_000
```

---

## 11. Confidence Model

### 11.1 Definition

``` text
confidence ∈ [0, 1]
```

---

### 11.2 Formula

``` text
confidence =
0.35 * freshness_score +
0.30 * residual_score +
0.20 * drift_score +
0.15 * jitter_score
```

---

### 11.3 Components

#### freshness_score

``` text
freshness_score = max(0, 1 - age_s / T)
```

Where:

- `age_s = time since last PPS`
- `T ≈ 5s`

---

#### residual_score

``` text
residual_score = max(0, 1 - |residual_us| / residual_limit)
```

---

#### drift_score

``` text
drift_score = max(0, 1 - |drift_ppm| / drift_limit)
```

---

#### jitter_score

``` text
jitter_score = max(0, 1 - |jitter_us| / jitter_limit)
```

---

### 11.4 State constraints

``` text
if LOST:
confidence ≤ 0.2

if HOLDOVER:
confidence ≤ 0.7
```

---

## 12. Summary

``` text
board_time_us → corrected_time
```

using:

- offset
- drift
- PPS anchor
- holdover
- confidence

---

## 13. Parameter Design and Rationale

This section explains the rationale behind key parameters used in the Time Engine.

These parameters are not arbitrarily chosen; each controls a specific behavior of the system.

---

### 13.1 alpha_offset

``` text
alpha_offset = 0.25
```

Controls how quickly the offset estimate reacts to new PPS measurements.

- Higher value:
  - faster convergence
  - more sensitive to jitter
- Lower value:
  - smoother offset
  - slower convergence

Chosen value (0.25) balances responsiveness and noise suppression.

---

### 13.2 alpha_drift

``` text
alpha_drift = 0.15
```

Controls smoothing of drift estimation.

- Higher value:
  - reacts faster to drift changes
  - may amplify noise
- Lower value:
  - more stable drift
  - slower adaptation

Chosen smaller than alpha_offset because drift is inherently noisier.

---

### 13.3 lock_min_pps

``` text
lock_min_pps = 3
```

Minimum number of consecutive valid PPS measurements required to enter LOCKED state.

- Too small:
  - risk false lock
- Too large:
  - slow lock acquisition

Value 3 provides basic stability without delaying lock.

---

### 13.4 lock_residual_threshold_us

``` text
lock_residual_threshold_us = 300
```

Threshold for acceptable offset residual during lock acquisition.

- Smaller threshold:
  - stricter lock condition
  - more robust but harder to lock
- Larger threshold:
  - easier to lock
  - risk inaccurate lock

300 µs is chosen based on expected PPS jitter scale.

---

### 13.5 relock_residual_threshold_us

``` text
relock_residual_threshold_us = 400
```

Threshold for re-locking after HOLDOVER.

- Slightly larger than lock threshold to allow faster recovery
- Prevents oscillation between states

---

### 13.6 holdover_timeout_us

``` text
holdover_timeout_us = 1.5e6
```

Time without PPS before entering HOLDOVER.

- Too small:
  - frequent unnecessary HOLDOVER
- Too large:
  - delayed detection of PPS loss

1.5 seconds allows tolerance for minor PPS jitter while detecting real outages.

---

### 13.7 lost_timeout_us

``` text
lost_timeout_us = 5e6
```

Time without PPS before entering LOST state.

- Defines maximum reliable HOLDOVER duration
- After this, drift uncertainty becomes too large

5 seconds is a conservative engineering choice for short-term holdover.

---

### 13.8 Summary

These parameters collectively control:

- convergence speed (alpha_offset)
- stability (alpha_drift)
- lock robustness (lock_min_pps, residual thresholds)
- fault tolerance (holdover_timeout, lost_timeout)

They are chosen to balance:

- responsiveness
- noise robustness
- system stability

and are suitable for a prototype-level Time Engine.