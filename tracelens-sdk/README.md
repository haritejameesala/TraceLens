# TraceLens Python SDK

Framework-independent context-manager instrumentation for Python applications. The SDK sends explicitly supplied metadata to a TraceLens backend; it does not automatically capture prompts, model inputs, or outputs.

## Install from this repository

    pip install -e ./tracelens-sdk

## Minimal example

    import os
    from tracelens_sdk import TraceLens

    with TraceLens(
        project_id=os.environ["TRACELENS_PROJECT_ID"],
        api_url=os.getenv("TRACELENS_API_URL", "http://127.0.0.1:8000"),
        api_key=os.getenv("TRACELENS_API_KEY") or None,
        strict=False,
    ) as tracer:
        with tracer.start_run("customer-support-answer", version="v1") as run:
            with run.trace_step("retrieve", event_type="retrieval", payload={"top_k": 5}):
                # Call your retriever and record metrics you explicitly choose.
                pass
            with run.trace_step("generate", event_type="generation", payload={"model": "your-model"}):
                # Call your model here.
                pass

## API

- TraceLens(project_id, api_url=..., timeout=8.0, strict=True, api_key=None) owns an HTTP client unless one is injected.
- start_run(name, version="dev", baseline_run_id=None, metadata=None) opens a run context and persists the final run status.
- run.trace_step(step, event_type="custom", payload=None, source_file=None, source_line=None) measures elapsed time and records failures.
- run.record_custom_event(...) records a point-in-time event.
- TraceEvent is available for explicit event construction.

Set strict=False to keep telemetry transport errors from breaking your application. Common sensitive dictionary keys are redacted, but redaction is best-effort: do not send secrets or private data. Use api_key when the backend's TRACELENS_API_KEY setting is enabled.
