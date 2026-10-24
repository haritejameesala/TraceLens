import json
import httpx
from tracelens_sdk import TraceLens, sanitize_payload, traced_step


def test_sanitize_payload_redacts_sensitive_keys_and_common_tokens():
    result = sanitize_payload({"api_key": "secret-value", "nested": {"password": "p@ss", "note": "token=abc123"}, "ok": 2})
    assert result["api_key"] == "[REDACTED]"
    assert result["nested"]["password"] == "[REDACTED]"
    assert "abc123" not in result["nested"]["note"]
    assert result["ok"] == 2


def test_trace_step_emits_start_and_finish_and_redacts_payload():
    calls = []
    def handler(req):
        body = req.read().decode()
        calls.append((req.method, req.url.path, body))
        if req.method == "POST" and req.url.path == "/api/runs":
            return httpx.Response(201, json={"run_id": "run-1"})
        return httpx.Response(200, json={"ok": True})
    tracer = TraceLens("p1", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        with tracer.start_run("test") as run:
            with run.trace_step("retrieve", event_type="retrieval", payload={"api_key": "supersecret", "count": 2}):
                pass
        event_bodies = [json.loads(body) for method, path, body in calls if method == "POST" and path.endswith("/events")]
        assert any(e["step"] == "retrieve.started" for e in event_bodies)
        end = next(e for e in event_bodies if e["step"] == "retrieve")
        assert end["payload"]["api_key"] == "[REDACTED]"
        assert end["payload"]["count"] == 2
    finally:
        tracer.close()


def test_traced_step_decorator_records_callable_failure_and_reraises():
    calls = []
    def handler(req):
        calls.append((req.method, req.url.path, req.read().decode()))
        if req.method == "POST" and req.url.path == "/api/runs":
            return httpx.Response(201, json={"run_id": "run-2"})
        return httpx.Response(200, json={"ok": True})
    tracer = TraceLens("p1", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        with tracer.start_run("decorator-test") as run:
            @traced_step(run, "model.invoke", event_type="generation", payload={"model": "fake"})
            def fail():
                raise ConnectionError("connection refused")
            try:
                fail()
            except ConnectionError:
                pass
        events = [json.loads(body) for method, path, body in calls if method == "POST" and path.endswith("/events")]
        assert any(e["step"] == "model.invoke" and e["status"] == "failed" for e in events)
    finally:
        tracer.close()


def test_structured_retrieval_and_generation_helpers_omit_raw_content():
    calls = []
    def handler(req):
        body = req.read().decode()
        calls.append((req.method, req.url.path, body))
        if req.method == "POST" and req.url.path == "/api/runs":
            return httpx.Response(201, json={"run_id": "run-telemetry"})
        return httpx.Response(200, json={"ok": True})
    tracer = TraceLens("p1", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        with tracer.start_run("telemetry-test") as run:
            run.record_retrieval(query="customer private question", retrieved_count=2,
                                 retriever="chroma", collection="support",
                                 chunks=[{"chunk_id": "chunk-1", "score": 0.82, "source": "billing.md", "text": "do not send"}])
            run.record_generation(provider="ollama", model="qwen2.5:1.5b", duration_ms=21.4,
                                  prompt_tokens=10, completion_tokens=8)
        bodies = [json.loads(body) for method, path, body in calls if method == "POST" and path.endswith("/events")]
        retrieval = next(e for e in bodies if e["step"] == "retrieval.summary")
        assert retrieval["payload"]["retrieved_chunk_count"] == 2
        assert retrieval["payload"]["query_fingerprint"]
        assert "customer private question" not in json.dumps(retrieval)
        assert "do not send" not in json.dumps(retrieval)
        generation = next(e for e in bodies if e["step"] == "generation.summary")
        assert generation["payload"]["model"] == "qwen2.5:1.5b"
        assert generation["trace_id"] == "run-telemetry"
    finally:
        tracer.close()
