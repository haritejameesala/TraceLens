"""Validated request models shared by the HTTP API."""
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator

def now(): return datetime.now(timezone.utc)
def make_id(prefix: str): return f"{prefix}_{uuid4().hex[:14]}"

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=800)
    framework: str = Field(default="python", max_length=80)

class RunCreate(BaseModel):
    project_id: str = Field(min_length=1, max_length=180)
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
    status: Literal["success", "failed", "warning"] = "success"
    timestamp: datetime = Field(default_factory=now)
    duration_ms: float | None = Field(default=None, ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)
    error: str | None = Field(default=None, max_length=3000)
    source_file: str | None = Field(default=None, max_length=300)
    source_line: int | None = Field(default=None, ge=1)
    @field_validator("step")
    @classmethod
    def step_is_not_blank(cls, value: str):
        if not value.strip(): raise ValueError("step must not be blank")
        return value.strip()

class CompareRequest(BaseModel):
    baseline_run_id: str = Field(min_length=1, max_length=180)
    current_run_id: str = Field(min_length=1, max_length=180)

class KnowledgeDocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=100000)
    source: str = Field(default="manual", max_length=500)
    @field_validator("title", "content")
    @classmethod
    def text_is_not_blank(cls, value: str):
        if not value.strip(): raise ValueError("value must not be blank")
        return value.strip()

class DiagnoseRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    run_id: str | None = Field(default=None, max_length=180)
    top_k: int = Field(default=5, ge=1, le=12)
