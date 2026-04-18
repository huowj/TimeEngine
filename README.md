# DSIL Time Engine Trial

This repository implements a host-side Time Engine prototype for DSIL SDK V1.

The prototype treats `board_time_us` as the only authoritative time axis and uses PPS as the timing anchor to estimate:

- corrected timestamp
- offset_us
- drift_ppm
- confidence
- sync_state (LOCKED / HOLDOVER / LOST)

It demonstrates:

- PPS lock acquisition
- multi-sensor timestamp correction
- drift tracking
- holdover when PPS is lost
- timing observability via metrics and plots

## Run

```bash
python3 tools/generate_mock_data.py
PYTHONPATH=. python3 tools/run_demo.py

