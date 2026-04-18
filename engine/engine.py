from dataclasses import dataclass, field
from typing import Dict, List, Optional

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

    # simple counters
    total_packets: int = 0
    total_pps: int = 0
    total_sensor: int = 0


class TimeEngine:
    def __init__(self) -> None:
        self.state = TimeEngineState()

        # smoothing
        self.alpha_offset = 0.25
        self.alpha_drift = 0.15

        # thresholds
        self.lock_min_pps = 3
        self.lock_residual_threshold_us = 300.0
        self.relock_residual_threshold_us = 400.0

        self.holdover_timeout_us = 1_500_000
        self.lost_timeout_us = 5_000_000

    def process_packet(self, packet: Packet) -> CorrectedEvent:
        self.state.total_packets += 1
        if packet.type == "TIMING_EVENT" and packet.source == "pps":
            self.state.total_pps += 1
            event = self._handle_pps(packet)
        else:
            self.state.total_sensor += 1
            event = self._handle_sensor(packet)

        self._record_state_snapshot()
        return event

    def _handle_pps(self, packet: Packet) -> CorrectedEvent:
        s = self.state

        if s.anchor_board_time_us is None:
            # First PPS defines anchor.
            # We align it to corrected second boundary = 1_000_000 us.
            s.anchor_board_time_us = packet.board_time_us
            s.anchor_target_time_us = 1_000_000
            target_time_us = s.anchor_target_time_us
        else:
            assert s.anchor_board_time_us is not None
            assert s.anchor_target_time_us is not None

            elapsed_us = packet.board_time_us - s.anchor_board_time_us
            elapsed_sec_rounded = max(0, int(round(elapsed_us / 1_000_000.0)))
            target_time_us = s.anchor_target_time_us + elapsed_sec_rounded * 1_000_000

            # Ensure monotonic target time
            if s.last_target_time_us is not None and target_time_us <= s.last_target_time_us:
                target_time_us = s.last_target_time_us + 1_000_000

        measured_offset_us = float(target_time_us - packet.board_time_us)

        predicted_offset_before_update = self._predict_offset(packet.board_time_us)
        residual_us = measured_offset_us - predicted_offset_before_update
        s.pps_residual_history.append(residual_us)

        # interval / jitter
        if s.last_pps_board_time_us is not None:
            interval_us = packet.board_time_us - s.last_pps_board_time_us

            expected_interval_us = 1_000_000
            if s.last_target_time_us is not None:
                target_interval_us = target_time_us - s.last_target_time_us
                if target_interval_us > 0:
                    expected_interval_us = target_interval_us

            jitter_us = interval_us - expected_interval_us
            s.pps_interval_jitter_history.append(float(jitter_us))

            dt_s = interval_us / 1_000_000.0
            if s.last_measured_offset_us is not None and dt_s > 0:
                measured_drift_ppm = (measured_offset_us - s.last_measured_offset_us) / dt_s
                s.drift_ppm = (
                    self.alpha_drift * measured_drift_ppm
                    + (1.0 - self.alpha_drift) * s.drift_ppm
                )

        # update offset after drift estimate
        if s.last_pps_board_time_us is None:
            s.offset_us = measured_offset_us
        else:
            s.offset_us = (
                self.alpha_offset * measured_offset_us
                + (1.0 - self.alpha_offset) * s.offset_us
            )

        # lock logic
        threshold = (
            self.relock_residual_threshold_us
            if s.sync_state in (SyncState.HOLDOVER, SyncState.LOST)
            else self.lock_residual_threshold_us
        )

        if abs(residual_us) < threshold:
            s.consecutive_good_pps += 1
        else:
            s.consecutive_good_pps = 1

        if s.consecutive_good_pps >= self.lock_min_pps:
            s.sync_state = SyncState.LOCKED

        s.last_pps_board_time_us = packet.board_time_us
        s.last_target_time_us = target_time_us
        s.last_measured_offset_us = measured_offset_us
        s.holdover_entry_board_time_us = None

        self._update_confidence(packet.board_time_us)

        corrected_us = packet.board_time_us + s.offset_us
        return CorrectedEvent(
            type=packet.type,
            source=packet.source,
            sensor_id=packet.sensor_id,
            board_time_us=packet.board_time_us,
            timestamp_corrected_us=corrected_us,
            offset_us=s.offset_us,
            drift_ppm=s.drift_ppm,
            confidence=s.confidence,
            sync_state=s.sync_state.value,
            payload=packet.payload,
        )

    def _handle_sensor(self, packet: Packet) -> CorrectedEvent:
        s = self.state
        self._update_state_for_missing_pps(packet.board_time_us)

        predicted_offset_us = self._predict_offset(packet.board_time_us)
        corrected_us = packet.board_time_us + predicted_offset_us

        self._update_confidence(packet.board_time_us)

        return CorrectedEvent(
            type=packet.type,
            source=packet.source,
            sensor_id=packet.sensor_id,
            board_time_us=packet.board_time_us,
            timestamp_corrected_us=corrected_us,
            offset_us=predicted_offset_us,
            drift_ppm=s.drift_ppm,
            confidence=s.confidence,
            sync_state=s.sync_state.value,
            payload=packet.payload,
        )

    def _predict_offset(self, board_time_us: int) -> float:
        s = self.state
        if s.last_pps_board_time_us is None:
            return s.offset_us

        dt_s = (board_time_us - s.last_pps_board_time_us) / 1_000_000.0
        return s.offset_us + s.drift_ppm * dt_s

    def _update_state_for_missing_pps(self, board_time_us: int) -> None:
        s = self.state
        if s.last_pps_board_time_us is None:
            s.sync_state = SyncState.LOST
            return

        gap_us = board_time_us - s.last_pps_board_time_us

        if s.sync_state == SyncState.LOCKED and gap_us > self.holdover_timeout_us:
            s.sync_state = SyncState.HOLDOVER
            if s.holdover_entry_board_time_us is None:
                s.holdover_entry_board_time_us = board_time_us

        if gap_us > self.lost_timeout_us:
            s.sync_state = SyncState.LOST

    def _update_confidence(self, board_time_us: int) -> None:
        s = self.state

        if s.last_pps_board_time_us is None:
            s.confidence = 0.0
            return

        age_s = max(0.0, (board_time_us - s.last_pps_board_time_us) / 1_000_000.0)

        if s.sync_state == SyncState.LOCKED:
            freshness_score = max(0.0, 1.0 - age_s / 2.0)
        elif s.sync_state == SyncState.HOLDOVER:
            freshness_score = max(0.0, 1.0 - age_s / 5.0)
        else:
            freshness_score = max(0.0, 0.3 - age_s / 10.0)

        residual = abs(s.pps_residual_history[-1]) if s.pps_residual_history else 1000.0
        residual_score = max(0.0, 1.0 - min(residual / 500.0, 1.0))

        jitter = abs(s.pps_interval_jitter_history[-1]) if s.pps_interval_jitter_history else 0.0
        jitter_score = max(0.0, 1.0 - min(jitter / 300.0, 1.0))

        drift_score = max(0.0, 1.0 - min(abs(s.drift_ppm) / 50.0, 1.0))

        confidence = (
            0.35 * freshness_score
            + 0.30 * residual_score
            + 0.20 * drift_score
            + 0.15 * jitter_score
        )

        if s.sync_state == SyncState.LOST:
            confidence = min(confidence, 0.2)
        elif s.sync_state == SyncState.HOLDOVER:
            confidence = min(confidence, 0.75)

        s.confidence = max(0.0, min(confidence, 1.0))

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
