"""Failure-mode tests for SDK instrumentation using an in-memory HTTP transport."""
import json
import httpx
import pytest
from tracelens_sdk import TraceLens


def make_tracer(calls):
    def handler(request):
        body = request.read().decode()
        calls.append((request.method, request.url.path, body))
        if request.method == "POST" and request.url.path == "/api/runs":
            return httpx.Response(201, json={"run_id": "run-matrix"})
        return httpx.Response(200, json={"status": "stored"})
    return TraceLens("project-matrix", http_client=httpx.Client(transport=httpx.MockTransport(handler)))


@pytest.mark.parametrize("exc", [
    SyntaxError("invalid syntax"),
    IndentationError("unexpected indent"),
    ModuleNotFoundError("No module named 'missing_dep'"),
    ImportError("cannot import name 'missing'"),
    TimeoutError("generation timed out"),
    ConnectionError("connection refused"),
    ValueError("malformed output"),
    RuntimeError("HTTP 503 Service Unavailable"),
])
def test_instrumented_python_failures_are_recorded_and_reraised(exc):
    calls = []
    tracer = make_tracer(calls)
    try:
        with pytest.raises(type(exc)):
            with tracer.start_run("failure-matrix") as run:
                with run.trace_step("pipeline.stage", event_type="generation"):
                    raise exc
        events = [json.loads(body) for method, path, body in calls
                  if method == "POST" and path.endswith("/events")]
        failed_step = next(e for e in events if e["step"] == "pipeline.stage" and e["status"] == "failed")
        run_end = next(e for e in events if e["step"] == "run.failed")
        assert failed_step["payload"]["exception_type"] == type(exc).__name__
        assert run_end["status"] == "failed"
        assert any(method == "PATCH" and json.loads(body)["status"] == "failed"
                   for method, path, body in calls if method == "PATCH")
    finally:
        tracer.close()


def test_keyboard_interrupt_is_recorded_as_failed_and_propagated():
    calls = []
    tracer = make_tracer(calls)
    try:
        with pytest.raises(KeyboardInterrupt):
            with tracer.start_run("cancelled-run") as run:
                with run.trace_step("long-operation"):
                    raise KeyboardInterrupt()
        events = [json.loads(body) for method, path, body in calls
                  if method == "POST" and path.endswith("/events")]
        assert any(e["step"] == "run.failed" and e["payload"].get("exception_type") == "KeyboardInterrupt" for e in events)
    finally:
        tracer.close()


def test_error_messages_redact_credentials_before_transmission():
    calls = []
    tracer = make_tracer(calls)
    try:
        with tracer.start_run("privacy-error") as run:
            with pytest.raises(RuntimeError):
                with run.trace_step("generation"):
                    raise RuntimeError("api_key=very-secret-token")
        bodies = [body for method, path, body in calls if method == "POST" and path.endswith("/events")]
        serialized = "\n".join(bodies)
        assert "very-secret-token" not in serialized
        assert "[REDACTED]" in serialized
    finally:
        tracer.close()


def test_non_strict_mode_survives_http_503_telemetry_failure():
    def handler(request):
        return httpx.Response(503, text="unavailable")
    tracer = TraceLens("project-offline", strict=False,
                       http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        with tracer.start_run("telemetry-offline") as run:
            assert run.run_id is None
    finally:
        tracer.close()


def test_nested_steps_link_to_parent_span_event():
    calls = []
    tracer = make_tracer(calls)
    try:
        with tracer.start_run("nested-steps") as run:
            with run.trace_step("chain"):
                with run.trace_step("retrieval", event_type="retrieval"):
                    pass
        events = [json.loads(body) for method, path, body in calls
                  if method == "POST" and path.endswith("/events")]
        parent_start = next(e for e in events if e["step"] == "chain.started")
        child_start = next(e for e in events if e["step"] == "retrieval.started")
        child_end = next(e for e in events if e["step"] == "retrieval")
        assert child_start["parent_event_id"] == parent_start["event_id"]
        assert child_end["parent_event_id"] == parent_start["event_id"]
    finally:
        tracer.close()


def test_separate_runs_have_separate_trace_ids():
    calls = []
    created = 0
    def handler(request):
        nonlocal created
        body = request.read().decode()
        calls.append((request.method, request.url.path, body))
        if request.method == "POST" and request.url.path == "/api/runs":
            created += 1
            return httpx.Response(201, json={"run_id": f"run-{created}"})
        return httpx.Response(200, json={"status": "stored"})
    tracer = TraceLens("project-matrix", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        with tracer.start_run("first") as first:
            first_id = first.trace_id
        with tracer.start_run("second") as second:
            second_id = second.trace_id
        assert first_id == "run-1"
        assert second_id == "run-2"
        assert first_id != second_id
    finally:
        tracer.close()
