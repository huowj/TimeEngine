import json
from pathlib import Path
import matplotlib.pyplot as plt


def load_metrics(path):
    metrics = []
    with open(path) as f:
        for line in f:
            metrics.append(json.loads(line))
    return metrics


def plot_metrics(metrics, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)

    times = [m["board_time_us"] / 1e6 for m in metrics]
    offset = [m["offset_us"] for m in metrics]
    drift = [m["drift_ppm"] for m in metrics]
    confidence = [m["confidence"] for m in metrics]

    # OFFSET
    plt.figure()
    plt.plot(times, offset)
    plt.title("Offset Trend")
    plt.xlabel("Time (s)")
    plt.ylabel("Offset (us)")
    plt.savefig(output_dir / "offset.png")
    plt.close()

    # DRIFT
    plt.figure()
    plt.plot(times, drift)
    plt.title("Drift Trend")
    plt.xlabel("Time (s)")
    plt.ylabel("Drift (ppm)")
    plt.savefig(output_dir / "drift.png")
    plt.close()

    # CONFIDENCE
    plt.figure()
    plt.plot(times, confidence)
    plt.title("Confidence Trend")
    plt.xlabel("Time (s)")
    plt.ylabel("Confidence")
    plt.savefig(output_dir / "confidence.png")
    plt.close()
