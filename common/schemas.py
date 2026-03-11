from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, Literal
from datetime import datetime, timezone
import uuid

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class Command(BaseModel):
    command_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Literal["setpoint", "read"]
    site: str
    device: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    issued_at: datetime = Field(default_factory=utcnow)
    deadline_ms: int = 5000

class ResultEvent(BaseModel):
    command_id: str
    site: str
    device: str
    worker_id: str
    status: Literal["ok", "error", "timeout"]
    duration_ms: int
    error: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    ts: datetime = Field(default_factory=utcnow)

class TelemetryEvent(BaseModel):
    site: str
    device: str
    worker_id: str
    points: Dict[str, float]
    ts: datetime = Field(default_factory=utcnow)

class HeartbeatEvent(BaseModel):
    site: str
    worker_id: str
    device_id: Optional[str] = None   # matches FlexibleResource.resource_external_id
    status: Literal["ok", "degraded", "error"] = "ok"
    connected_devices: int = 0
    last_io_ts: Optional[datetime] = None
    version: str = "0.1.0"
    ts: datetime = Field(default_factory=utcnow)
