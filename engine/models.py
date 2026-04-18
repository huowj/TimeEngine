from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class SyncState(str, Enum):
    LOST = "LOST"
    LOCKED = "LOCKED"
    HOLDOVER = "HOLDOVER"


@dataclass
class Packet:
    type: str
    board_time_us: int
    source: Optional[str] = None
    sensor_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Packet":
        return Packet(
            type=data["type"],
            board_time_us=int(data["board_time_us"]),
            source=data.get("source"),
            sensor_id=data.get("sensor_id"),
            payload=data.get("payload", {}),
        )


@dataclass
class CorrectedEvent:
    type: str
    board_time_us: int
    timestamp_corrected_us: float
    offset_us: float
    drift_ppm: float
    confidence: float
    sync_state: str
    source: Optional[str] = None
    sensor_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "source": self.source,
            "sensor_id": self.sensor_id,
            "board_time_us": self.board_time_us,
            "timestamp_corrected_us": round(self.timestamp_corrected_us, 3),
            "offset_us": round(self.offset_us, 3),
            "drift_ppm": round(self.drift_ppm, 6),
            "confidence": round(self.confidence, 4),
            "sync_state": self.sync_state,
            "payload": self.payload or {},
        }
