from __future__ import annotations
import time
import traceback
import logging
import hashlib
import json
import os
import platform
from datetime import datetime, timezone
from contextlib import AbstractContextManager
from typing import Any
import httpx
from .events import TraceEvent
from .privacy import sanitize_payload

logger = logging.getLogger("tracelens.sdk")

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
            if "json" in kwargs and isinstance(kwargs["json"], dict):
                body = dict(kwargs["json"])
                if isinstance(body.get("metadata"), dict):
                    body["metadata"] = sanitize_payload(body["metadata"])
                if isinstance(body.get("payload"), dict):
                    body["payload"] = sanitize_payload(body["payload"])
                if isinstance(body.get("error"), str):
                    body["error"] = sanitize_text(body["error"])
                kwargs["json"] = body
            response = self._http.request(method, self.api_url + path, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None
        except Exception as exc:
            logger.warning("TraceLens delivery failed (%s %s): %s", method, path, type(exc).__name__)
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
        self.started_at = None
        self._finished = False
        self.trace_id = None

    def __enter__(self):
        self.started_at = time.perf_counter()
        data = self.tracer._request("POST", "/api/runs", json={
            "project_id": self.tracer.project_id, "scenario": self.name,
            "version": self.version, "baseline_run_id": self.baseline_run_id,
            "status": "running", "metadata": self.metadata,
        })
        self.run_id = data.get("run_id") if isinstance(data, dict) else None
        self.trace_id = self.run_id
        if not self.run_id and self.tracer.strict:
            raise RuntimeError("TraceLens failed to create a run")
        if self.run_id:
            self.record_event(TraceEvent(
                step="run.started", event_type="custom", status="success",
                payload={"lifecycle": "start", "run_name": self.name, "version": self.version,
                         "sdk_version": _sdk_version(), "python_version": platform.python_version(),
                         "platform": platform.system(), "started_at": datetime.now(timezone.utc).isoformat()},
                trace_id=self.trace_id,
            ))
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

    def record_retrieval(self, *, query: str, retrieved_count: int, retriever: str | None = None,
                         collection: str | None = None, chunks: list[dict[str, Any]] | None = None,
                         duration_ms: float | None = None):
        """Record retrieval metrics without storing raw query text by default.

        ``chunks`` should contain only safe identifiers/scores/source labels, not full chunk text.
        """
        query_hash = hashlib.sha256(query.encode("utf-8", errors="replace")).hexdigest() if query else None
        payload: dict[str, Any] = {"retrieved_chunk_count": max(0, int(retrieved_count)),
                                   "query_fingerprint": query_hash, "query_length": len(query or "")}
        if retriever: payload["retriever"] = retriever[:160]
        if collection: payload["collection"] = collection[:160]
        if chunks is not None:
            safe_chunks = []
            for chunk in chunks[:50]:
                if not isinstance(chunk, dict): continue
                item = {k: chunk[k] for k in ("chunk_id", "source", "score", "rank") if k in chunk}
                safe_chunks.append(item)
            payload["chunks"] = safe_chunks
        self.record_event(TraceEvent(step="retrieval.summary", event_type="retrieval", status="success",
                                     payload=payload, duration_ms=duration_ms, trace_id=self.trace_id))

    def record_generation(self, *, provider: str | None = None, model: str | None = None,
                          duration_ms: float | None = None, prompt_tokens: int | None = None,
                          completion_tokens: int | None = None, finish_reason: str | None = None,
                          status: str = "success", error: str | None = None):
        """Record generation metadata and usage without storing prompt or answer content."""
        payload: dict[str, Any] = {}
        if provider: payload["provider"] = provider[:120]
        if model: payload["model"] = model[:160]
        if prompt_tokens is not None: payload["prompt_tokens"] = max(0, int(prompt_tokens))
        if completion_tokens is not None: payload["completion_tokens"] = max(0, int(completion_tokens))
        if finish_reason: payload["finish_reason"] = finish_reason[:120]
        self.record_event(TraceEvent(step="generation.summary", event_type="generation" if status == "success" else "error",
                                     status=status, payload=payload, duration_ms=duration_ms, error=error, trace_id=self.trace_id))

    def record_custom_event(self, *, step: str, event_type: str = "custom",
                            status: str = "success", payload: dict[str, Any] | None = None,
                            error: str | None = None):
        self.record_event(TraceEvent(step=step, event_type=event_type, status=status,
                                     payload=payload or {}, error=error, trace_id=self.trace_id))

    def __exit__(self, exc_type, exc, tb):
        if self.run_id and not self._finished:
            failed = exc is not None
            duration_ms = round((time.perf_counter() - self.started_at) * 1000, 3) if self.started_at else None
            safe_error = sanitize_text(f"{type(exc).__name__}: {exc}")[:1000] if failed else None
            payload = {"lifecycle": "finish", "duration_ms": duration_ms,
                       "finished_at": datetime.now(timezone.utc).isoformat()}
            if failed:
                payload["exception_type"] = type(exc).__name__
                # Tracebacks can contain local values/secrets; retain only a bounded
                # stack summary and never serialize exception locals.
                # Traceback strings may contain request data; store only frame locations, never locals/messages.
                frames = traceback.extract_tb(tb) if tb else []
                payload["stack_frames"] = [{"file": f.filename, "line": f.lineno, "function": f.name} for f in frames[-8:]]
            self.record_event(TraceEvent(
                step="run.failed" if failed else "run.completed",
                event_type="error" if failed else "custom",
                status="failed" if failed else "success", payload=payload,
                duration_ms=duration_ms, error=safe_error, trace_id=self.trace_id,
            ))
            self.tracer._request("PATCH", f"/api/runs/{self.run_id}", json={
                "status": "failed" if failed else "success"
            })
            self._finished = True
        return False

class TraceStep(AbstractContextManager):
    def __init__(self, run, step, event_type, payload, source_file, source_line):
        if not step.strip():
            raise ValueError("step must not be empty")
        self.run, self.step, self.event_type = run, step, event_type
        self.payload, self.source_file, self.source_line = payload, source_file, source_line
        self.started = 0.0
        self.step_id = None

    def __enter__(self):
        self.started = time.perf_counter()
        from uuid import uuid4
        self.step_id = f"step_{uuid4().hex}"
        self.run.record_event(TraceEvent(
            step=f"{self.step}.started"[:120], event_type=self.event_type,
            status="running", payload={"phase": "start", "step_id": self.step_id,
                         "started_at": datetime.now(timezone.utc).isoformat(), **sanitize_payload(self.payload)},
            source_file=self.source_file, source_line=self.source_line, trace_id=self.run.trace_id,
        ))
        return self

    def __exit__(self, exc_type, exc, tb):
        duration = round((time.perf_counter() - self.started) * 1000, 3)
        failed = exc is not None
        payload = sanitize_payload(dict(self.payload))
        payload.update({"phase": "error" if failed else "end", "step_id": self.step_id})
        error = sanitize_text(f"{type(exc).__name__}: {exc}")[:1000] if failed else None
        event_type = "error" if failed else self.event_type
        if failed:
            payload["exception_type"] = type(exc).__name__
            frames = traceback.extract_tb(tb) if tb else []
            payload["stack_frames"] = [{"file": f.filename, "line": f.lineno, "function": f.name} for f in frames[-8:]]
        self.run.record_event(TraceEvent(
            step=self.step, event_type=event_type,
            status="failed" if failed else "success", payload=payload,
            duration_ms=duration, error=error,
            source_file=self.source_file, source_line=self.source_line, trace_id=self.run.trace_id,
        ))
        return False


def sanitize_text(value: str) -> str:
    """Redact common credential patterns from error strings before transmission."""
    import re
    text = str(value)
    patterns = [
        (r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+", r"\1[REDACTED]"),
        (r"(?i)(api[_-]?key|access[_-]?token|secret|password|token)(\s*[:=]\s*)[^\s,;]+", r"\1\2[REDACTED]"),
        (r"(?i)sk-[A-Za-z0-9_-]{12,}", "[REDACTED_KEY]"),
    ]
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    return text


def _sdk_version() -> str:
    try:
        from . import __version__
        return __version__
    except Exception:
        return "unknown"
