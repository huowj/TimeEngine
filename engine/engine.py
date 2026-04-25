from dataclasses import dataclass, field
from typing import Dict, List, Optional
import math

from .models import CorrectedEvent, Packet, SyncState
from .logger import info, warn


@dataclass
class TimeEngineState:
    offset_us: float = 0.0
    drift_ppm: float = 0.0
    confidence: float = 0.0
    sync_state: SyncState = SyncState.LOST

    anchor_board_time_us: Optional[int] = None
    anchor_target_time_us: Optional[int] = None

    last_pps_board_time_us: Optional[int] = None
    last_target_time_us: Optional[int] = None
    last_measured_offset_us: Optional[float] = None

    last_board_time_us: Optional[int] = None
    last_corrected_us: Optional[float] = None

    consecutive_good_pps: int = 0
    holdover_entry_board_time_us: Optional[int] = None

    pps_residual_history: List[float] = field(default_factory=list)
    pps_interval_jitter_history: List[float] = field(default_factory=list)
    pps_drift_history: List[float] = field(default_factory=list)
    drift_history: List[float] = field(default_factory=list)
    offset_history: List[float] = field(default_factory=list)
    confidence_history: List[float] = field(default_factory=list)
    state_history: List[str] = field(default_factory=list)

    total_packets: int = 0
    total_pps: int = 0
    total_sensor: int = 0


class TimeEngine:
    def __init__(self) -> None:
        self.state = TimeEngineState()

        self.alpha_offset = 0.25
        self.alpha_drift = 0.15

        self.lock_min_pps = 3
        self.lock_residual_threshold_us = 300.0
        self.relock_residual_threshold_us = 800.0
        self.unlock_residual_threshold_us = 1200.0

        self.holdover_timeout_us = 1_500_000
        self.lost_timeout_us = 5_000_000

        self.outlier_threshold_us = 3000.0
        self.max_drift_ppm = 50.0

        self.lock_jitter_threshold_us = 200.0
        self.lock_drift_stability_ppm = 5.0
        self.lock_drift_window = 3

        self.confidence_window = 5

        self.conf_residual_limit_us = 500.0
        self.conf_jitter_limit_us = 300.0
        self.conf_residual_std_limit_us = 300.0
        self.conf_jitter_std_limit_us = 200.0

        self.holdover_confidence_tau_s = 3.0
        self.holdover_confidence_cap = 0.7

    # =========================
    def _is_jitter_stable(self, jitter_us: float) -> bool:
        return abs(jitter_us) < self.lock_jitter_threshold_us


    def _is_drift_stable(self, current_drift: Optional[float] = None) -> bool:
        s = self.state

        history = s.pps_drift_history[:]
        if current_drift is not None:
            history.append(float(current_drift))

        if len(history) < self.lock_drift_window:
            return True

        recent = history[-self.lock_drift_window:]
        return max(recent) - min(recent) < self.lock_drift_stability_ppm

    def _window(self, values, n):
        return values[-n:] if len(values) >= n else values


    def _std_score(self, values, limit):
        if len(values) < 2:
            return 1.0

        mean = sum(values) / len(values)
        var = sum((x - mean) ** 2 for x in values) / len(values)
        std = math.sqrt(var)

        return max(0.0, 1.0 - std / limit)

    # =========================
    def process_packet(self, packet: Packet) -> CorrectedEvent:
        s = self.state
        s.total_packets += 1

        # monotonic guard
        if s.last_board_time_us is not None:
            if packet.board_time_us <= s.last_board_time_us:
                warn(f"Non-monotonic board_time detected: {packet.board_time_us}")
                packet.board_time_us = s.last_board_time_us + 1
        s.last_board_time_us = packet.board_time_us

        if packet.type == "TIMING_EVENT" and packet.source == "pps":
            s.total_pps += 1
            event = self._handle_pps(packet)
        else:
            s.total_sensor += 1
            event = self._handle_sensor(packet)

        self._record_state_snapshot()
        return event

    # =========================
    def _handle_pps(self, packet: Packet) -> CorrectedEvent:
        s = self.state

        if s.anchor_board_time_us is None:
            s.anchor_board_time_us = packet.board_time_us
            s.anchor_target_time_us = 1_000_000
            target_time_us = s.anchor_target_time_us
        else:
            elapsed_us = packet.board_time_us - s.anchor_board_time_us
            elapsed_sec = max(0, int(round(elapsed_us / 1_000_000.0)))
            target_time_us = s.anchor_target_time_us + elapsed_sec * 1_000_000

            if s.last_target_time_us and target_time_us <= s.last_target_time_us:
                target_time_us = s.last_target_time_us + 1_000_000

        measured_offset_us = float(target_time_us - packet.board_time_us)
        predicted_offset = self._predict_offset(packet.board_time_us)
        residual_us = measured_offset_us - predicted_offset

        # ===== first PPS bootstrap =====
        if s.last_pps_board_time_us is None:
            s.offset_us = measured_offset_us
            s.drift_ppm = 0.0
            s.consecutive_good_pps = 1

            s.last_pps_board_time_us = packet.board_time_us
            s.last_target_time_us = target_time_us
            s.last_measured_offset_us = measured_offset_us

            info(f"First PPS anchor established, offset={measured_offset_us:.2f}")
            self._update_confidence(packet.board_time_us)
            return self._build_corrected_event(packet)

        s.pps_residual_history.append(residual_us)

        # ===== outlier =====
        warmup = s.consecutive_good_pps < self.lock_min_pps
        if not warmup and abs(residual_us) > self.outlier_threshold_us:
            warn(f"PPS outlier rejected: residual={residual_us:.2f}")
            s.consecutive_good_pps = 0

            # rejected PPS 不更新 last_pps_board_time_us / target_time / measured_offset
            # 否则会污染后续 drift、dt_s 和 holdover 判断
            self._update_confidence(packet.board_time_us)
            return self._build_corrected_event(packet)

        # ===== drift =====
        interval_us = packet.board_time_us - s.last_pps_board_time_us
        jitter_us = interval_us - 1_000_000
        s.pps_interval_jitter_history.append(float(jitter_us))

        dt_s = interval_us / 1_000_000.0
        if s.last_measured_offset_us is not None and dt_s > 0:
            drift = (measured_offset_us - s.last_measured_offset_us) / dt_s
            drift = max(min(drift, self.max_drift_ppm), -self.max_drift_ppm)

            s.drift_ppm = (
                self.alpha_drift * drift +
                (1 - self.alpha_drift) * s.drift_ppm
            )
            s.pps_drift_history.append(float(s.drift_ppm))

        # ===== offset =====
        s.offset_us = (
            self.alpha_offset * measured_offset_us +
            (1 - self.alpha_offset) * s.offset_us
        )

        # ===== lock / unlock / relock logic =====

        jitter_ok = self._is_jitter_stable(jitter_us)
        drift_ok = self._is_drift_stable(s.drift_ppm)

        lock_residual_ok = abs(residual_us) < self.lock_residual_threshold_us
        relock_residual_ok = abs(residual_us) < self.relock_residual_threshold_us
        unlock_residual_bad = abs(residual_us) > self.unlock_residual_threshold_us

        # LOCKED 状态不要太敏感，避免 normal 误 HOLDOVER
        if s.sync_state == SyncState.LOCKED:
            if unlock_residual_bad:
                warn("LOCKED -> HOLDOVER (residual too large)")
                s.consecutive_good_pps = 0
                s.sync_state = SyncState.HOLDOVER
            else:
                # LOCKED 中的小抖动不退出，只维持状态
                s.consecutive_good_pps = min(
                    s.consecutive_good_pps + 1,
                    self.lock_min_pps
                )

        else:
            # LOST 初次锁定更严格
            if s.sync_state == SyncState.LOST:
                residual_ok = lock_residual_ok
            else:
                # HOLDOVER 后 relock 应该更宽松
                residual_ok = relock_residual_ok

            if residual_ok and jitter_ok:
                s.consecutive_good_pps += 1
            else:
                s.consecutive_good_pps = max(0, s.consecutive_good_pps - 1)

            if (
                s.consecutive_good_pps >= self.lock_min_pps
                and residual_ok
                and jitter_ok
                and drift_ok
            ):
                info(f"LOCKED after {s.consecutive_good_pps} PPS")
                s.sync_state = SyncState.LOCKED

        s.last_pps_board_time_us = packet.board_time_us
        s.last_target_time_us = target_time_us
        s.last_measured_offset_us = measured_offset_us
        s.holdover_entry_board_time_us = None

        self._update_confidence(packet.board_time_us)

        return self._build_corrected_event(packet)

    # =========================
    def _handle_sensor(self, packet: Packet) -> CorrectedEvent:
        s = self.state

        self._update_state_for_missing_pps(packet.board_time_us)

        predicted_offset = self._predict_offset(packet.board_time_us)
        corrected_us = packet.board_time_us + predicted_offset

        if s.last_corrected_us is not None:
            if corrected_us <= s.last_corrected_us:
                warn("Corrected time not monotonic, fixing")
                corrected_us = s.last_corrected_us + 1

        s.last_corrected_us = corrected_us

        self._update_confidence(packet.board_time_us)

        return CorrectedEvent(
            type=packet.type,
            source=packet.source,
            sensor_id=packet.sensor_id,
            board_time_us=packet.board_time_us,
            timestamp_corrected_us=corrected_us,
            offset_us=predicted_offset,
            drift_ppm=s.drift_ppm,
            confidence=s.confidence,
            sync_state=s.sync_state.value,
            payload=packet.payload,
        )

    # =========================
    def _predict_offset(self, board_time_us: int) -> float:
        s = self.state
        if s.last_pps_board_time_us is None:
            return s.offset_us

        dt_s = (board_time_us - s.last_pps_board_time_us) / 1_000_000.0
        drift = max(min(s.drift_ppm, self.max_drift_ppm), -self.max_drift_ppm)

        return s.offset_us + drift * dt_s

    # =========================
    def _update_state_for_missing_pps(self, board_time_us: int) -> None:
        s = self.state

        if s.last_pps_board_time_us is None:
            s.sync_state = SyncState.LOST
            return

        gap_us = board_time_us - s.last_pps_board_time_us

        if s.sync_state == SyncState.LOCKED and gap_us > self.holdover_timeout_us:
            warn(f"Enter HOLDOVER at t={board_time_us}")
            s.sync_state = SyncState.HOLDOVER
            s.holdover_entry_board_time_us = board_time_us

        if gap_us > self.lost_timeout_us:
            warn("Enter LOST (PPS missing too long)")
            s.sync_state = SyncState.LOST

    # =========================
    def _update_confidence(self, board_time_us: int) -> None:
        s = self.state

        if s.last_pps_board_time_us is None:
            s.confidence = 0.0
            return

        age_s = (board_time_us - s.last_pps_board_time_us) / 1_000_000.0

        residuals = self._window(
            [abs(x) for x in s.pps_residual_history],
            self.confidence_window
        )

        jitters = self._window(
            [abs(x) for x in s.pps_interval_jitter_history],
            self.confidence_window
        )

        # freshness
        if s.sync_state == SyncState.HOLDOVER:
            freshness_score = math.exp(-age_s / self.holdover_confidence_tau_s)
        else:
            freshness_score = max(0.0, 1.0 - age_s / 2.0)

        # level quality
        residual_mean = sum(residuals) / len(residuals) if residuals else self.conf_residual_limit_us
        jitter_mean = sum(jitters) / len(jitters) if jitters else 0.0

        residual_score = max(
            0.0,
            1.0 - residual_mean / self.conf_residual_limit_us
        )

        jitter_score = max(
            0.0,
            1.0 - jitter_mean / self.conf_jitter_limit_us
        )

        # stability quality
        residual_stability_score = self._std_score(
            residuals,
            self.conf_residual_std_limit_us
        )

        jitter_stability_score = self._std_score(
            jitters,
            self.conf_jitter_std_limit_us
        )

        drift_score = max(
            0.0,
            1.0 - abs(s.drift_ppm) / self.max_drift_ppm
        )

        confidence = (
            0.25 * freshness_score +
            0.25 * residual_score +
            0.15 * jitter_score +
            0.15 * residual_stability_score +
            0.10 * jitter_stability_score +
            0.10 * drift_score
        )

        if s.sync_state == SyncState.HOLDOVER:
            confidence = min(confidence, self.holdover_confidence_cap)
            confidence *= freshness_score

        if s.sync_state == SyncState.LOST:
            confidence = min(confidence, 0.2)

        s.confidence = max(0.0, min(confidence, 1.0))

    # =========================
    def _build_corrected_event(self, packet: Packet) -> CorrectedEvent:
        s = self.state

        predicted_offset = self._predict_offset(packet.board_time_us)
        corrected = packet.board_time_us + predicted_offset

        if s.last_corrected_us is not None:
            if corrected <= s.last_corrected_us:
                corrected = s.last_corrected_us + 1

        s.last_corrected_us = corrected

        return CorrectedEvent(
            type=packet.type,
            source=packet.source,
            sensor_id=packet.sensor_id,
            board_time_us=packet.board_time_us,
            timestamp_corrected_us=corrected,
            offset_us=predicted_offset,
            drift_ppm=s.drift_ppm,
            confidence=s.confidence,
            sync_state=s.sync_state.value,
            payload=packet.payload,
        )

    def _record_state_snapshot(self) -> None:
        s = self.state
        s.offset_history.append(float(s.offset_us))
        s.drift_history.append(float(s.drift_ppm))
        s.confidence_history.append(float(s.confidence))
        s.state_history.append(s.sync_state.value)

    def get_summary(self) -> Dict[str, float]:
        s = self.state
        return {
            "total_packets": s.total_packets,
            "total_pps": s.total_pps,
            "total_sensor": s.total_sensor,
            "final_offset_us": s.offset_us,
            "final_drift_ppm": s.drift_ppm,
            "final_confidence": s.confidence,
        }
