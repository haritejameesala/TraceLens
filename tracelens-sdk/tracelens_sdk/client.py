from __future__ import annotations
import time
import traceback
from contextlib import AbstractContextManager
from typing import Any
import httpx
from .events import TraceEvent

class TraceLens:
    """HTTP client for TraceLens. Only explicitly supplied metadata is captured."""
    def __init__(self, project_id: str, api_url: str = "http://127.0.0.1:8000",
                 timeout: float = 8.0, strict: bool = True,
                 http_client: httpx.Client | None = None):
        if not project_id or not project_id.strip():
            raise ValueError("project_id must be a non-empty string")
        self.project_id = project_id
        self.api_url = api_url.rstrip("/")
        self.strict = strict
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout)

    def _request(self, method: str, path: str, **kwargs):
        try:
            response = self._http.request(method, self.api_url + path, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None
        except Exception:
            if self.strict:
                raise
            return None

    def start_run(self, name: str, *, version: str = "dev",
                  baseline_run_id: str | None = None,
                  metadata: dict[str, Any] | None = None):
        if not name.strip():
            raise ValueError("run name must not be empty")
        return TraceRun(self, name, version, baseline_run_id, metadata or {})

    def close(self):
        if self._owns_client:
            self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

class TraceRun(AbstractContextManager):
    def __init__(self, tracer, name, version, baseline_run_id, metadata):
        self.tracer, self.name, self.version = tracer, name, version
        self.baseline_run_id, self.metadata = baseline_run_id, metadata
        self.run_id = None

    def __enter__(self):
        data = self.tracer._request("POST", "/api/runs", json={
            "project_id": self.tracer.project_id, "scenario": self.name,
            "version": self.version, "baseline_run_id": self.baseline_run_id,
            "status": "running", "metadata": self.metadata,
        })
        self.run_id = data.get("run_id") if isinstance(data, dict) else None
        if not self.run_id and self.tracer.strict:
            raise RuntimeError("TraceLens failed to create a run")
        return self

    def trace_step(self, step: str, *, event_type: str = "custom",
                   payload: dict[str, Any] | None = None,
                   source_file: str | None = None, source_line: int | None = None):
        return TraceStep(self, step, event_type, payload if payload is not None else {},
                         source_file, source_line)

    def record_event(self, event: TraceEvent):
        if not self.run_id:
            if self.tracer.strict:
                raise RuntimeError("Cannot record event without a persisted run ID")
            return
        self.tracer._request("POST", f"/api/runs/{self.run_id}/events", json=event.to_dict())

    def record_custom_event(self, *, step: str, event_type: str = "custom",
                            status: str = "success", payload: dict[str, Any] | None = None,
                            error: str | None = None):
        self.record_event(TraceEvent(step=step, event_type=event_type, status=status,
                                     payload=payload or {}, error=error))

    def __exit__(self, exc_type, exc, tb):
        if self.run_id:
            self.tracer._request("PATCH", f"/api/runs/{self.run_id}", json={
                "status": "failed" if exc is not None else "success"
            })
        return False

class TraceStep(AbstractContextManager):
    def __init__(self, run, step, event_type, payload, source_file, source_line):
        if not step.strip():
            raise ValueError("step must not be empty")
        self.run, self.step, self.event_type = run, step, event_type
        self.payload, self.source_file, self.source_line = payload, source_file, source_line
        self.started = 0.0

    def __enter__(self):
        self.started = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        duration = round((time.perf_counter() - self.started) * 1000, 3)
        failed = exc is not None
        payload = dict(self.payload)
        error = f"{type(exc).__name__}: {exc}" if failed else None
        event_type = "error" if failed else self.event_type
        if failed:
            payload["exception_type"] = type(exc).__name__
            payload["traceback"] = "".join(traceback.format_exception(type(exc), exc, tb))[-5000:]
        self.run.record_event(TraceEvent(
            step=self.step, event_type=event_type,
            status="failed" if failed else "success", payload=payload,
            duration_ms=duration, error=error,
            source_file=self.source_file, source_line=self.source_line,
        ))
        return False
