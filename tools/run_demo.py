import csv
import json
from collections import Counter
from pathlib import Path
from statistics import mean

import matplotlib.pyplot as plt

from engine import Packet, TimeEngine


INPUT_PATH = Path("sample_packets/mock_stream.jsonl")
CORRECTED_OUTPUT_PATH = Path("outputs/corrected_events.jsonl")
METRICS_OUTPUT_PATH = Path("outputs/metrics.csv")
SUMMARY_OUTPUT_PATH = Path("outputs/summary.txt")

OFFSET_PLOT_PATH = Path("outputs/offset_trend.png")
DRIFT_PLOT_PATH = Path("outputs/drift_trend.png")
CONFIDENCE_PLOT_PATH = Path("outputs/confidence_trend.png")


def percentile(values, p):
    if not values:
        return 0.0
    values = sorted(values)
    if len(values) == 1:
        return float(values[0])
    rank = (len(values) - 1) * p
    low = int(rank)
    high = min(low + 1, len(values) - 1)
    frac = rank - low
    return float(values[low] * (1 - frac) + values[high] * frac)


def write_metrics_csv(rows):
    METRICS_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "index",
        "type",
        "source",
        "sensor_id",
        "board_time_us",
        "timestamp_corrected_us",
        "offset_us",
        "drift_ppm",
        "confidence",
        "sync_state",
    ]
    with METRICS_OUTPUT_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def plot_series(x, y, title, xlabel, ylabel, output_path):
    plt.figure(figsize=(10, 4))
    plt.plot(x, y)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(output_path, dpi=160)
    plt.close()


def write_summary(summary_lines):
    SUMMARY_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_OUTPUT_PATH.open("w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines) + "\n")


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"{INPUT_PATH} not found. Please run: python3 tools/generate_mock_data.py"
        )

    CORRECTED_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    engine = TimeEngine()
    corrected_count = 0
    metrics_rows = []

    with INPUT_PATH.open("r", encoding="utf-8") as fin, CORRECTED_OUTPUT_PATH.open("w", encoding="utf-8") as fout:
        for index, line in enumerate(fin):
            raw = json.loads(line)
            packet = Packet.from_dict(raw)
            corrected = engine.process_packet(packet)
            corrected_dict = corrected.to_dict()

            fout.write(json.dumps(corrected_dict) + "\n")
            corrected_count += 1

            metrics_rows.append(
                {
                    "index": index,
                    "type": corrected_dict["type"],
                    "source": corrected_dict.get("source"),
                    "sensor_id": corrected_dict.get("sensor_id"),
                    "board_time_us": corrected_dict["board_time_us"],
                    "timestamp_corrected_us": corrected_dict["timestamp_corrected_us"],
                    "offset_us": corrected_dict["offset_us"],
                    "drift_ppm": corrected_dict["drift_ppm"],
                    "confidence": corrected_dict["confidence"],
                    "sync_state": corrected_dict["sync_state"],
                }
            )

    write_metrics_csv(metrics_rows)

    x = list(range(len(metrics_rows)))
    offsets = [row["offset_us"] for row in metrics_rows]
    drifts = [row["drift_ppm"] for row in metrics_rows]
    confidences = [row["confidence"] for row in metrics_rows]

    plot_series(
        x,
        offsets,
        "Offset Trend",
        "Event Index",
        "Offset (us)",
        OFFSET_PLOT_PATH,
    )
    plot_series(
        x,
        drifts,
        "Drift Trend",
        "Event Index",
        "Drift (ppm)",
        DRIFT_PLOT_PATH,
    )
    plot_series(
        x,
        confidences,
        "Confidence Trend",
        "Event Index",
        "Confidence",
        CONFIDENCE_PLOT_PATH,
    )

    residuals = engine.state.pps_residual_history
    jitters = engine.state.pps_interval_jitter_history
    state_counter = Counter(engine.state.state_history)
    summary = engine.get_summary()

    summary_lines = [
        "DSIL Time Engine Demo Summary",
        "=============================",
        "",
        f"Input file: {INPUT_PATH}",
        f"Corrected events file: {CORRECTED_OUTPUT_PATH}",
        f"Metrics file: {METRICS_OUTPUT_PATH}",
        "",
        f"Total packets: {summary['total_packets']}",
        f"Total PPS events: {summary['total_pps']}",
        f"Total sensor events: {summary['total_sensor']}",
        "",
        f"Final sync state: {engine.state.sync_state.value}",
        f"Final offset_us: {summary['final_offset_us']:.3f}",
        f"Final drift_ppm: {summary['final_drift_ppm']:.6f}",
        f"Final confidence: {summary['final_confidence']:.4f}",
        "",
        f"State counts: {dict(state_counter)}",
        "",
        f"PPS residual mean us: {mean(residuals):.3f}" if residuals else "PPS residual mean us: 0.000",
        f"PPS residual p50 us: {percentile(residuals, 0.50):.3f}" if residuals else "PPS residual p50 us: 0.000",
        f"PPS residual p95 us: {percentile(residuals, 0.95):.3f}" if residuals else "PPS residual p95 us: 0.000",
        "",
        f"PPS jitter mean us: {mean(jitters):.3f}" if jitters else "PPS jitter mean us: 0.000",
        f"PPS jitter p50 us: {percentile(jitters, 0.50):.3f}" if jitters else "PPS jitter p50 us: 0.000",
        f"PPS jitter p95 us: {percentile(jitters, 0.95):.3f}" if jitters else "PPS jitter p95 us: 0.000",
        "",
        f"Offset plot: {OFFSET_PLOT_PATH}",
        f"Drift plot: {DRIFT_PLOT_PATH}",
        f"Confidence plot: {CONFIDENCE_PLOT_PATH}",
    ]
    write_summary(summary_lines)

    print("Demo completed")
    print(f"Input file:  {INPUT_PATH}")
    print(f"Output file: {CORRECTED_OUTPUT_PATH}")
    print(f"Metrics file: {METRICS_OUTPUT_PATH}")
    print(f"Summary file: {SUMMARY_OUTPUT_PATH}")
    print(f"Corrected events: {corrected_count}")
    print(f"Final sync state: {engine.state.sync_state.value}")
    print(f"Final offset_us: {engine.state.offset_us:.3f}")
    print(f"Final drift_ppm: {engine.state.drift_ppm:.6f}")
    print(f"Final confidence: {engine.state.confidence:.4f}")
    print(f"Plots: {OFFSET_PLOT_PATH}, {DRIFT_PLOT_PATH}, {CONFIDENCE_PLOT_PATH}")


if __name__ == "__main__":
    main()
