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


def compute_offset_continuity(metrics):
    deltas = []
    prev = None

    for m in metrics:
        offset = m["offset_us"]
        if offset is None:
            continue

        if prev is not None:
            deltas.append(abs(offset - prev))
        prev = offset

    if not deltas:
        return None

    return {
        "max_jump": max(deltas),
        "p95": np.percentile(deltas, 95),
    }


def compute_holdover_drift_growth(metrics):
    values = []

    for m in metrics:
        if m["state"] == "HOLDOVER":
            values.append(m["offset_us"])

    if len(values) < 2:
        return None

    return abs(values[-1] - values[0])


def compute_confidence_behavior(metrics):
    holdover_conf = []
    post_lock_conf = []

    in_holdover = False

    for m in metrics:
        if m["state"] == "HOLDOVER":
            in_holdover = True
            holdover_conf.append(m["confidence"])

        elif in_holdover:
            if m["state"] == "LOCKED":
                post_lock_conf.append(m["confidence"])

    if not holdover_conf:
        return None

    degraded = min(holdover_conf) < 0.7
    recovered = max(post_lock_conf) > 0.8 if post_lock_conf else False

    return {
        "degraded": degraded,
        "recovered": recovered
    }
