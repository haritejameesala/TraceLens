import httpx
import pytest
from tracelens_sdk import TraceLens


def client_with(handler, strict=True):
    return TraceLens("project-test", strict=strict, http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_run_lifecycle_records_step_and_closes_successfully():
    calls = []
    def handler(req):
        calls.append((req.method, req.url.path, req.read().decode()))
        if req.method == "POST" and req.url.path == "/api/runs":
            return httpx.Response(201, json={"run_id": "run-test"})
        return httpx.Response(200, json={"status": "stored"})
    tracer = client_with(handler)
    with tracer.start_run("test") as run:
        with run.trace_step("retrieval", event_type="retrieval", payload={"retrieved_chunk_count": 2}):
            pass
    assert any(path == "/api/runs/run-test/events" for _, path, _ in calls)
    assert any(method == "PATCH" and path == "/api/runs/run-test" for method, path, _ in calls)
    tracer.close()


def test_non_strict_mode_survives_backend_unavailable():
    def handler(req):
        raise httpx.ConnectError("offline", request=req)
    tracer = client_with(handler, strict=False)
    with tracer.start_run("offline") as run:
        assert run.run_id is None
    tracer.close()


def test_empty_project_rejected():
    with pytest.raises(ValueError):
        TraceLens(" ")
