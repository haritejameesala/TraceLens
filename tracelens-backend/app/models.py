from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict
from uuid import uuid4
def now(): return datetime.now(timezone.utc)
def make_id(prefix): return f"{prefix}_{uuid4().hex[:14]}"
class ProjectCreate(BaseModel):
    project_key: str | None = Field(default=None, min_length=3, max_length=160, pattern=r"^[a-z0-9][a-z0-9._:-]*$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=800)
    framework: str = Field(default="python", max_length=80)
class ProjectUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=800)
    framework: str = Field(default="python", max_length=80)
class RunDetailsUpdate(BaseModel):
    scenario: str = Field(min_length=1, max_length=150)
class RunCreate(BaseModel):
    project_id: str
    scenario: str = Field(min_length=1, max_length=150)
    version: str = Field(default="dev", max_length=100)
    baseline_run_id: str | None = None
    status: Literal["running", "success", "failed"] = "running"
    metadata: dict[str, Any] = Field(default_factory=dict)
class RunUpdate(BaseModel):
    status: Literal["running", "success", "failed"]
class EventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=1, max_length=180)
    step: str = Field(min_length=1, max_length=120)
    event_type: Literal["retrieval", "context", "generation", "validation", "error", "custom"]
    status: Literal["running", "success", "failed", "warning"] = "success"
    timestamp: datetime = Field(default_factory=now)
    duration_ms: float | None = Field(default=None, ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)
    error: str | None = Field(default=None, max_length=3000)
    source_file: str | None = Field(default=None, max_length=300)
    source_line: int | None = Field(default=None, ge=1)
    trace_id: str | None = Field(default=None, max_length=180)
    parent_event_id: str | None = Field(default=None, max_length=180)
class CompareRequest(BaseModel):
    baseline_run_id: str
    current_run_id: str
