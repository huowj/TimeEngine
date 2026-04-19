from dataclasses import dataclass, field
from typing import Dict, List, Optional
import math

from .models import CorrectedEvent, Packet, SyncState


@dataclass
class TimeEngineState:
    offset_us: float = 0.0
    drift_ppm: float = 0.0
    confidence: float = 0.0
    sync_state: SyncState = SyncState.LOST

    # PPS anchor model
    anchor_board_time_us: Optional[int] = None
    anchor_target_time_us: Optional[int] = None

    last_pps_board_time_us: Optional[int] = None
    last_target_time_us: Optional[int] = None
    last_measured_offset_us: Optional[float] = None

    # monotonic guards
    last_board_time_us: Optional[int] = None
    last_corrected_us: Optional[float] = None

    # state / tracking
    consecutive_good_pps: int = 0
    holdover_entry_board_time_us: Optional[int] = None

    # observability histories
    pps_residual_history: List[float] = field(default_factory=list)
    pps_interval_jitter_history: List[float] = field(default_factory=list)
    drift_history: List[float] = field(default_factory=list)
    offset_history: List[float] = field(default_factory=list)
    confidence_history: List[float] = field(default_factory=list)
    state_history: List[str] = field(default_factory=list)

    # counters
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
        self.relock_residual_threshold_us = 400.0

        self.holdover_timeout_us = 1_500_000
        self.lost_timeout_us = 5_000_000

        # robustness thresholds
        self.outlier_threshold_us = 3000.0
        self.max_drift_ppm = 50.0

    # =========================
    # Entry
    # =========================
    def process_packet(self, packet: Packet) -> CorrectedEvent:
        s = self.state
        s.total_packets += 1

        # ===== board_time monotonic guard =====
        if s.last_board_time_us is not None:
            if packet.board_time_us <= s.last_board_time_us:
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
    # PPS
    # =========================
    def _handle_pps(self, packet: Packet) -> CorrectedEvent:
        s = self.state

        # ===== Anchor =====
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

        # ===== FIRST PPS BOOTSTRAP =====
        if s.last_pps_board_time_us is None:
            s.offset_us = measured_offset_us
            s.drift_ppm = 0.0
            s.consecutive_good_pps = 1

            s.last_pps_board_time_us = packet.board_time_us
            s.last_target_time_us = target_time_us
            s.last_measured_offset_us = measured_offset_us

            self._update_confidence(packet.board_time_us)
            return self._build_corrected_event(packet)

        # ===== 记录 residual =====
        s.pps_residual_history.append(residual_us)

        # ===== OUTLIER（冷启动放宽）=====
        warmup = s.consecutive_good_pps < 3
        if not warmup and abs(residual_us) > self.outlier_threshold_us:
            s.consecutive_good_pps = 0
            return self._build_corrected_event(packet)

        # ===== jitter / drift =====
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

        # ===== offset update =====
        s.offset_us = (
            self.alpha_offset * measured_offset_us +
            (1 - self.alpha_offset) * s.offset_us
        )

        # ===== LOCK LOGIC（冷启动放宽）=====
        if s.sync_state == SyncState.LOCKED:
            # 已锁定：允许轻微波动，不掉锁
            if abs(residual_us) > self.outlier_threshold_us:
                s.consecutive_good_pps = 0
                s.sync_state = SyncState.HOLDOVER
        else:
            # 未锁定：严格判断
            if warmup:
                s.consecutive_good_pps += 1
            else:
                threshold = self.relock_residual_threshold_us

                if abs(residual_us) < threshold:
                    s.consecutive_good_pps += 1
                else:
                    s.consecutive_good_pps = 1

        if s.consecutive_good_pps >= self.lock_min_pps:
            if s.sync_state != SyncState.LOCKED:
                print(f"[INFO] LOCKED after {s.consecutive_good_pps} PPS")
            s.sync_state = SyncState.LOCKED

        # ===== update state =====
        s.last_pps_board_time_us = packet.board_time_us
        s.last_target_time_us = target_time_us
        s.last_measured_offset_us = measured_offset_us
        s.holdover_entry_board_time_us = None

        self._update_confidence(packet.board_time_us)

        return self._build_corrected_event(packet)

    # =========================
    # SENSOR
    # =========================
    def _handle_sensor(self, packet: Packet) -> CorrectedEvent:
        s = self.state

        self._update_state_for_missing_pps(packet.board_time_us)

        predicted_offset = self._predict_offset(packet.board_time_us)

        corrected_us = packet.board_time_us + predicted_offset

        # ===== corrected monotonic guard =====
        if s.last_corrected_us is not None:
            if corrected_us <= s.last_corrected_us:
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
    # Predict
    # =========================
    def _predict_offset(self, board_time_us: int) -> float:
        s = self.state
        if s.last_pps_board_time_us is None:
            return s.offset_us

        dt_s = (board_time_us - s.last_pps_board_time_us) / 1_000_000.0

        drift = max(min(s.drift_ppm, self.max_drift_ppm), -self.max_drift_ppm)

        return s.offset_us + drift * dt_s

    # =========================
    # State
    # =========================
    def _update_state_for_missing_pps(self, board_time_us: int) -> None:
        s = self.state

        if s.last_pps_board_time_us is None:
            s.sync_state = SyncState.LOST
            return

        gap_us = board_time_us - s.last_pps_board_time_us

        if s.sync_state == SyncState.LOCKED and gap_us > self.holdover_timeout_us:
            s.sync_state = SyncState.HOLDOVER
            s.holdover_entry_board_time_us = board_time_us

        if gap_us > self.lost_timeout_us:
            s.sync_state = SyncState.LOST

    # =========================
    # Confidence
    # =========================
    def _update_confidence(self, board_time_us: int) -> None:
        s = self.state

        if s.last_pps_board_time_us is None:
            s.confidence = 0.0
            return

        age_s = (board_time_us - s.last_pps_board_time_us) / 1_000_000.0

        # ===== exponential decay in HOLDOVER =====
        if s.sync_state == SyncState.HOLDOVER:
            freshness = math.exp(-age_s / 3.0)
        else:
            freshness = max(0.0, 1.0 - age_s / 2.0)

        residual = abs(s.pps_residual_history[-1]) if s.pps_residual_history else 1000
        residual_score = max(0, 1 - residual / 500)

        jitter = abs(s.pps_interval_jitter_history[-1]) if s.pps_interval_jitter_history else 0
        jitter_score = max(0, 1 - jitter / 300)

        drift_score = max(0, 1 - abs(s.drift_ppm) / 50)

        confidence = (
            0.35 * freshness +
            0.30 * residual_score +
            0.20 * drift_score +
            0.15 * jitter_score
        )

        if s.sync_state == SyncState.LOST:
            confidence = min(confidence, 0.2)

        s.confidence = max(0.0, min(confidence, 1.0))

    # =========================
    def _build_corrected_event(self, packet: Packet) -> CorrectedEvent:
        s = self.state
        corrected = packet.board_time_us + s.offset_us

        return CorrectedEvent(
            type=packet.type,
            source=packet.source,
            sensor_id=packet.sensor_id,
            board_time_us=packet.board_time_us,
            timestamp_corrected_us=corrected,
            offset_us=s.offset_us,
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
