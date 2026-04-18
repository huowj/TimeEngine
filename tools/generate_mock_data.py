import json
import random
from pathlib import Path


OUTPUT_PATH = Path("sample_packets/mock_stream.jsonl")


def board_time_from_true_time_us(
    true_time_us: float,
    initial_offset_us: float,
    drift_ppm: float,
) -> int:
    drift_term_us = drift_ppm * (true_time_us / 1_000_000.0)
    board_time_us = true_time_us - initial_offset_us + drift_term_us
    return int(round(board_time_us))


def main() -> None:
    random.seed(7)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    duration_s = 12.0
    initial_offset_us = 3500.0
    drift_ppm = 12.0

    events = []

    # PPS: 1 Hz
    # Simulate a PPS outage between 6s and 7s
    pps_seconds = [sec for sec in range(1, int(duration_s) + 1) if sec not in (6, 7)]
    for sec in pps_seconds:
        true_time_us = sec * 1_000_000.0
        jitter_us = random.gauss(0.0, 25.0)

        board_time_us = board_time_from_true_time_us(
            true_time_us + jitter_us,
            initial_offset_us,
            drift_ppm,
        )

        events.append(
            {
                "type": "TIMING_EVENT",
                "source": "pps",
                "board_time_us": board_time_us,
                "payload": {},
            }
        )

    # IMU: 100 Hz
    imu_period_us = 10_000
    imu_count = int(duration_s * 100)
    for i in range(imu_count):
        true_time_us = i * imu_period_us
        jitter_us = random.gauss(0.0, 80.0)

        board_time_us = board_time_from_true_time_us(
            true_time_us + jitter_us,
            initial_offset_us,
            drift_ppm,
        )

        events.append(
            {
                "type": "SENSOR_EVENT",
                "sensor_id": "imu_vn100_0",
                "board_time_us": board_time_us,
                "payload": {},
            }
        )

    # Camera: 30 Hz
    cam_period_us = 1_000_000.0 / 30.0
    cam_count = int(duration_s * 30)
    for i in range(cam_count):
        true_time_us = i * cam_period_us
        jitter_us = random.gauss(0.0, 250.0)

        board_time_us = board_time_from_true_time_us(
            true_time_us + jitter_us,
            initial_offset_us,
            drift_ppm,
        )

        events.append(
            {
                "type": "SENSOR_EVENT",
                "sensor_id": "camera_front_0",
                "board_time_us": board_time_us,
                "payload": {},
            }
        )

    events.sort(key=lambda x: x["board_time_us"])

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    print(f"Wrote {len(events)} events to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
