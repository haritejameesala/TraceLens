# TraceLens Python SDK API (0.4.x)

## `TraceLens(project_id, api_url=..., timeout=8.0, strict=True, http_client=None)`

Creates an HTTP client for the TraceLens backend. `strict=True` raises delivery errors; `strict=False` logs a safe warning and allows the application to continue. Non-strict mode can lose telemetry when the backend is unavailable, so monitor delivery failures separately.

- `start_run(name, version="dev", baseline_run_id=None, metadata=None) -> TraceRun`
- `close()` / context manager: closes only an internally created HTTP client.

## `TraceRun`

- `run_id`: backend-assigned run ID, or `None` when creation failed in non-strict mode.
- `trace_step(step, event_type="custom", payload=None, source_file=None, source_line=None)`: emits a start event and a terminal success/failure event; exceptions propagate.
- `record_event(TraceEvent(...))`: sends a custom event.
- `record_custom_event(step=..., event_type=..., status=..., payload=..., error=...)`: convenience method.

Run context exit emits `run.completed` or `run.failed` and updates run status. Exception stack frames are recorded without local variables; payload and error strings receive best-effort secret redaction.

## `traced_step(run, step, event_type="custom", payload=None)`

Decorator for instrumenting a callable inside an existing run. Arguments and return values are not captured automatically.

## Optional LangChain integration

Install `pip install 'tracelens-sdk[langchain]'` and pass `langchain_callback(...)` through LangChain's supported `config={"callbacks": [...]}` mechanism. Only framework callback boundaries are observed; arbitrary functions, startup work before invocation, and external system logs are not automatically visible.

## Data safety

Redaction is best effort, not a privacy guarantee. Do not submit credentials, full prompts, completions, customer records, or document bodies by default. Prefer counts, stable IDs, source labels, durations, versions, and allowlisted metadata. Treat exception messages as potentially sensitive.
