import json
import random
import argparse
from pathlib import Path

from engine import Packet, TimeEngine
from tools.metrics_utils import (
    compute_time_to_lock,
    compute_holdover_duration,
    compute_relock_pps,
    compute_residual_stats,
    compute_jitter_stats,
    compute_confidence_stats,
)


# =========================
# Mock 数据生成
# =========================

def board_time_from_true_time_us(true_time_us, offset_us, drift_ppm):
    drift_term = drift_ppm * (true_time_us / 1_000_000.0)
    return int(round(true_time_us - offset_us + drift_term))


def generate_events(scenario: str):
    random.seed(7)

    duration_s = 12
    offset_us = 3500.0
    drift_ppm = 12.0

    events = []

    # 场景控制
    if scenario == "normal":
        pps_drop = []
        pps_outlier = {}

    elif scenario == "holdover":
        pps_drop = [6, 7, 8, 9]  # 丢失 PPS
        pps_outlier = {}

    elif scenario == "jitter_outlier":
        pps_drop = []
        pps_outlier = {5: 5000}  # 第5秒异常

    else:
        raise ValueError("Unknown scenario")

    # PPS
    for sec in range(1, duration_s + 1):
        if sec in pps_drop:
            continue

        true_time_us = sec * 1_000_000
        jitter = random.gauss(0, 25)

        if sec in pps_outlier:
            jitter += pps_outlier[sec]

        bt = board_time_from_true_time_us(true_time_us + jitter, offset_us, drift_ppm)

        events.append({
            "type": "TIMING_EVENT",
            "source": "pps",
            "board_time_us": bt,
        })

    # IMU (100Hz)
    for i in range(duration_s * 100):
        true_time_us = i * 10_000
        jitter = random.gauss(0, 80)

        bt = board_time_from_true_time_us(true_time_us + jitter, offset_us, drift_ppm)

        events.append({
            "type": "SENSOR_EVENT",
            "sensor_id": "imu_vn100_0",
            "board_time_us": bt,
        })

    # Camera (30Hz)
    cam_period = 1_000_000 / 30
    for i in range(duration_s * 30):
        true_time_us = i * cam_period
        jitter = random.gauss(0, 250)

        bt = board_time_from_true_time_us(true_time_us + jitter, offset_us, drift_ppm)

        events.append({
            "type": "SENSOR_EVENT",
            "sensor_id": "camera_front_0",
            "board_time_us": bt,
        })

    events.sort(key=lambda x: x["board_time_us"])
    return events


# =========================
# Demo 主流程
# =========================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="normal",
                        choices=["normal", "holdover", "jitter_outlier"])
    args = parser.parse_args()

    # 生成数据
    events = generate_events(args.scenario)

    # 输出目录
    output_dir = Path(f"outputs/{args.scenario}")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "corrected_events.jsonl"
    summary_file = output_dir / "summary.txt"

    engine = TimeEngine()

    metrics = []

    state_changes = []
    last_state = None

    # 跑 engine
    with output_file.open("w") as fout:
        for e in events:
            packet = Packet.from_dict(e)
            corrected = engine.process_packet(packet)
            metrics.append({
                "board_time_us": packet.board_time_us,
                "state": corrected.sync_state,
                "offset": corrected.offset_us,
                "drift": corrected.drift_ppm,
                "confidence": corrected.confidence,
                "residual": engine.state.pps_residual_history[-1]
                    if engine.state.pps_residual_history else None,
                "jitter": engine.state.pps_interval_jitter_history[-1]
                    if engine.state.pps_interval_jitter_history else None,
            })

            fout.write(json.dumps(corrected.to_dict()) + "\n")

            # 记录状态变化
            current_state = corrected.sync_state
            if current_state != last_state:
                state_changes.append(
                    (packet.board_time_us, current_state)
                )
                last_state = current_state

    time_to_lock = compute_time_to_lock(metrics)
    holdover_duration = compute_holdover_duration(metrics)
    relock_pps = compute_relock_pps(metrics)

    residual_stats = compute_residual_stats(metrics)
    jitter_stats = compute_jitter_stats(metrics)
    confidence_stats = compute_confidence_stats(metrics)

    # 写 summary
    with summary_file.open("w") as f:
        f.write(f"Scenario: {args.scenario}\n")
        f.write(f"Total events: {len(events)}\n")
        f.write(f"Final state: {engine.state.sync_state.value}\n")
        f.write(f"Final offset_us: {engine.state.offset_us:.2f}\n")
        f.write(f"Final drift_ppm: {engine.state.drift_ppm:.2f}\n")
        f.write(f"Final confidence: {engine.state.confidence:.3f}\n\n")

        # ===== Observability =====
        f.write("=== Observability Metrics ===\n")

        f.write(f"Time to LOCKED: {time_to_lock:.2f} s\n" if time_to_lock else "Time to LOCKED: N/A\n")
        f.write(f"Holdover duration: {holdover_duration:.2f} s\n")
        f.write(f"Relock PPS count: {relock_pps}\n\n")

        if residual_stats:
            f.write("Residual stats (us):\n")
            f.write(f"  p50: {residual_stats['p50']:.2f}\n")
            f.write(f"  p95: {residual_stats['p95']:.2f}\n")
            f.write(f"  max: {residual_stats['max']:.2f}\n\n")

        if jitter_stats:
            f.write("Jitter stats (us):\n")
            f.write(f"  p50: {jitter_stats['p50']:.2f}\n")
            f.write(f"  p95: {jitter_stats['p95']:.2f}\n")
            f.write(f"  max: {jitter_stats['max']:.2f}\n\n")

        if confidence_stats:
            f.write("Confidence:\n")
            f.write(f"  min: {confidence_stats['min']:.3f}\n")
            f.write(f"  recovery_time: {confidence_stats['recovery_time_s']}\n\n")

        f.write("State transitions:\n")
        for t, s in state_changes:
            f.write(f"  {t} us -> {s}\n")

    # 控制台输出
    print("====================================")
    print(f"Scenario: {args.scenario}")
    print(f"Events processed: {len(events)}")
    print(f"Final state: {engine.state.sync_state.value}")
    print(f"Offset: {engine.state.offset_us:.2f}")
    print(f"Drift: {engine.state.drift_ppm:.2f}")
    print(f"Confidence: {engine.state.confidence:.3f}")
    print("====================================")


if __name__ == "__main__":
    main()
