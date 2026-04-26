# Time Engine Delivery

## 1. Demo Execution

The following scenarios were executed:

```bash
python3 -m tools.run_demo --scenario normal
python3 -m tools.run_demo --scenario holdover
python3 -m tools.run_demo --scenario jitter_outlier
python3 -m tools.run_demo --scenario drift_jump
```

## 2. Generated Artifacts

Each scenario output is available under:

```text
outputs/<scenario>/
```

Required artifacts:

| Scenario | summary.txt | metrics.jsonl | offset.png | drift.png | confidence.png |
|---|---|---|---|---|---|
| normal | yes | yes | yes | yes | yes |
| holdover | yes | yes | yes | yes | yes |
| jitter_outlier | yes | yes | yes | yes | yes |
| drift_jump | yes | yes | yes | yes | yes |

Additional artifacts:

- `corrected_events.jsonl`
- `run.log`

Expected output structure:

```text
outputs/
├── normal/
│   ├── summary.txt
│   ├── metrics.jsonl
│   ├── corrected_events.jsonl
│   ├── offset.png
│   ├── drift.png
│   ├── confidence.png
│   └── run.log
├── holdover/
│   ├── summary.txt
│   ├── metrics.jsonl
│   ├── corrected_events.jsonl
│   ├── offset.png
│   ├── drift.png
│   ├── confidence.png
│   └── run.log
├── jitter_outlier/
│   ├── summary.txt
│   ├── metrics.jsonl
│   ├── corrected_events.jsonl
│   ├── offset.png
│   ├── drift.png
│   ├── confidence.png
│   └── run.log
└── drift_jump/
    ├── summary.txt
    ├── metrics.jsonl
    ├── corrected_events.jsonl
    ├── offset.png
    ├── drift.png
    ├── confidence.png
    └── run.log
```

## 3. Pytest Validation

Validation command:

```bash
pytest -q
```

Validation log:

```text
validation/pytest.log
```

Result:

```text
<Paste exact pytest output here>
```

## 4. Time Model Document

Authoritative time model document:

```text
docs/time_model.md
```

The document defines:

- offset model
- drift model
- PPS discipline strategy
- LOCKED / HOLDOVER / LOST state transitions
- confidence calculation and interpretation
- outlier rejection behavior
- holdover behavior

## 5. Reproduction Commands

To regenerate all scenario outputs:

```bash
python3 -m tools.run_demo --scenario normal | tee outputs/normal/run.log
python3 -m tools.run_demo --scenario holdover | tee outputs/holdover/run.log
python3 -m tools.run_demo --scenario jitter_outlier | tee outputs/jitter_outlier/run.log
python3 -m tools.run_demo --scenario drift_jump | tee outputs/drift_jump/run.log
```

To run validation:

```bash
pytest -q | tee validation/pytest.log
```

## 6. Acceptance Checklist

A delivery is considered complete when:

- [ ] all four required scenarios run successfully
- [ ] each scenario generates `summary.txt`
- [ ] each scenario generates `metrics.jsonl`
- [ ] each scenario generates `offset.png`
- [ ] each scenario generates `drift.png`
- [ ] each scenario generates `confidence.png`
- [ ] `pytest -q` passes
- [ ] `validation/pytest.log` is included
- [ ] `docs/time_model.md` is included
- [ ] `docs/time_model.md` matches the current implementation

## 7. Payment Note

Payment can be released after the reviewer confirms that:

1. all four required scenarios run successfully
2. all required artifacts are present
3. `pytest -q` passes
4. `docs/time_model.md` satisfies the DSIL SDK time model specification requirement
5. the delivery artifacts are committed to the GitHub repository
