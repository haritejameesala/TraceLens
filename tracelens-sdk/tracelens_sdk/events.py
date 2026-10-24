from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

def utc_now():
    return datetime.now(timezone.utc)

@dataclass
class TraceEvent:
    step: str
    event_type: str = "custom"
    status: str = "success"
    payload: dict[str, Any] = field(default_factory=dict)
    duration_ms: float | None = None
    error: str | None = None
    source_file: str | None = None
    source_line: int | None = None
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex}")
    timestamp: datetime = field(default_factory=utc_now)
    parent_event_id: str | None = None
    trace_id: str | None = None

    def to_dict(self):
        result = {
            "event_id": self.event_id, "step": self.step,
            "event_type": self.event_type, "status": self.status,
            "payload": self.payload, "timestamp": self.timestamp.isoformat(),
        }
        for key in ("duration_ms", "error", "source_file", "source_line", "parent_event_id", "trace_id"):
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        return result
