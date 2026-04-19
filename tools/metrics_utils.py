import numpy as np


def compute_time_to_lock(metrics):
    start = None
    for m in metrics:
        if m["state"] != "LOST":
            start = m["board_time_us"]
            break

    for m in metrics:
        if m["state"] == "LOCKED":
            return (m["board_time_us"] - start) / 1e6

    return None


def compute_holdover_duration(metrics):
    durations = []
    start = None

    for m in metrics:
        if m["state"] == "HOLDOVER" and start is None:
            start = m["board_time_us"]

        elif m["state"] != "HOLDOVER" and start is not None:
            durations.append((m["board_time_us"] - start) / 1e6)
            start = None

    return max(durations) if durations else 0


def compute_relock_pps(metrics):
    count = 0
    in_holdover = False

    for m in metrics:
        if m["state"] == "HOLDOVER":
            in_holdover = True
            count = 0

        elif in_holdover:
            if m["state"] == "LOCKED":
                return count

            if m["residual"] is not None:
                count += 1

    return None


def compute_residual_stats(metrics):
    values = [abs(m["residual"]) for m in metrics if m["residual"] is not None]
    if not values:
        return None

    return {
        "p50": np.percentile(values, 50),
        "p95": np.percentile(values, 95),
        "max": max(values),
    }


def compute_jitter_stats(metrics):
    values = [abs(m["jitter"]) for m in metrics if m["jitter"] is not None]
    if not values:
        return None

    return {
        "p50": np.percentile(values, 50),
        "p95": np.percentile(values, 95),
        "max": max(values),
    }


def compute_confidence_stats(metrics):
    values = [m["confidence"] for m in metrics]

    min_conf = min(values)

    recovery_time = None
    for m in metrics:
        if m["confidence"] > 0.8:
            recovery_time = m["board_time_us"]
            break

    return {
        "min": min_conf,
        "recovery_time_s": recovery_time / 1e6 if recovery_time else None
    }
