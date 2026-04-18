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

### 2.2 Anchor semantics

PPS is the only timing anchor.

PPS does not introduce a new free-running time source.  
Instead, PPS provides a recurring absolute second-boundary constraint that allows the Time Engine to estimate the mapping from `board_time_us` to corrected time.

### 2.3 Output semantics

Arrival time is not truth.

The only time value exported by the Time Engine is:

- `timestamp_corrected_us`

This value is computed from the engine state and should be treated as the externally usable event timestamp.

---

## 3. Event Types

The engine accepts packets equivalent to:

```json
{
  "type": "TIMING_EVENT | SENSOR_EVENT",
  "sensor_id": "imu_vn100_0",
  "board_time_us": 1000234,
  "payload": {}
}

