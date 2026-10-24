"""Small instrumentation helpers for custom Python pipelines."""
from __future__ import annotations
from functools import wraps
from typing import Any, Callable, TypeVar
from .privacy import sanitize_payload

F = TypeVar("F", bound=Callable[..., Any])

def traced_step(run, step: str, *, event_type: str = "custom", payload: dict[str, Any] | None = None):
    """Instrument a callable inside an existing TraceRun.

    Example::
        @traced_step(run, "retrieve", event_type="retrieval")
        def retrieve(question): ...

    Only the explicitly supplied static payload is recorded; arguments and return
    values are not captured automatically.
    """
    def decorate(func: F) -> F:
        @wraps(func)
        def wrapped(*args, **kwargs):
            with run.trace_step(step, event_type=event_type, payload=sanitize_payload(payload or {})):
                return func(*args, **kwargs)
        return wrapped  # type: ignore[return-value]
    return decorate
