# TraceLens Python SDK

A Python toolkit for instrumenting RAG execution, sending trace events to the TraceLens backend, and enabling evidence-based diagnostics. Python SDKs do not normally need to ship a compiler or IDE; this package supplies a client library, framework integration, instrumentation helpers, examples, tests, and API/security documentation.

## Install

From the SDK directory:

```powershell
python -m pip install .
# Optional LangChain callback integration
python -m pip install ".[langchain]"
# Development/test tooling
python -m pip install ".[dev]"
```

Editable local development install:

```powershell
python -m pip install -e ".[dev,langchain]"
```

## Quick start

```python
import os
from tracelens_sdk import TraceLens

with TraceLens(
    project_id=os.environ["TRACELENS_PROJECT_ID"],
    api_url=os.getenv("TRACELENS_API_URL", "http://127.0.0.1:8000"),
    strict=True,
) as tracer:
    with tracer.start_run("support-rag", version="1.2.0", metadata={"environment": "staging"}) as run:
        with run.trace_step("retrieve", event_type="retrieval", payload={"top_k": 4}):
            retrieved_ids = ["kb-001", "kb-009"]  # replace with actual retrieval
        run.record_custom_event(
            step="retrieval.summary", event_type="retrieval",
            payload={"retrieved_chunk_count": len(retrieved_ids), "chunk_ids": retrieved_ids},
        )
        with run.trace_step("generate", event_type="generation", payload={"model": "your-model"}):
            answer = "Replace with your model invocation"
```

See [`examples/custom_rag.py`](examples/custom_rag.py), [`docs/API.md`](docs/API.md), and [`docs/SECURITY.md`](docs/SECURITY.md).

## Structured retrieval and generation telemetry

Use the helpers when a framework callback does not expose enough application-specific detail:

```python
with tracer.start_run("support-rag", version="1.2.0") as run:
    # Do not pass raw customer content or complete document text.
    run.record_retrieval(
        query=question,  # only a SHA-256 fingerprint and length are stored
        retrieved_count=len(documents),
        retriever="chroma",
        collection="support-kb",
        chunks=[{"chunk_id": d.metadata.get("chunk_id"),
                 "source": d.metadata.get("source"),
                 "score": d.metadata.get("score")} for d in documents],
    )
    answer = model.invoke(prompt)
    run.record_generation(provider="ollama", model="qwen2.5:1.5b",
                          duration_ms=elapsed_ms)
```

These helpers deliberately avoid capturing raw query, prompt, answer, or document text. The caller should provide only safe identifiers and numeric scores. For exact stage start/end timing and exceptions, prefer `run.trace_step(...)` around the actual operation.

## Automatic LangChain instrumentation

```python
from tracelens_sdk import TraceLens, langchain_callback

with TraceLens(project_id=project_id, api_url=api_url, strict=False) as tracer:
    callback = langchain_callback(tracer, run_name="support-rag", version="1.0.0")
    answer = chain.invoke({"question": question}, config={"callbacks": [callback]})
```

The integration observes supported LangChain callback boundaries. It does not automatically instrument arbitrary Python code, application startup, or external system logs. Add `traced_step` or `run.trace_step(...)` around custom operations.

## Reliability and privacy

- `strict=True` raises telemetry delivery failures; `strict=False` logs safe warnings and lets application work continue, but events may be lost.
- The SDK emits run lifecycle and step start/finish events and preserves exceptions by re-raising them.
- Secret-like keys and common token patterns are redacted best-effort. This is not a substitute for data minimization; never send secrets or full customer content by default.
- SDK events are sent to the TraceLens HTTP API, not directly to MongoDB.

## Test

```powershell
python -m pip install ".[dev,langchain]"
python -m pytest
```

## Versioning

The SDK follows semantic versioning. Public API changes and event-schema changes are documented in `CHANGELOG.md`. Version `0.4.0` adds lifecycle start events, which consumers should tolerate as additive events.

## Capturing startup/import failures

The SDK can only capture exceptions after instrumentation begins. To capture Python syntax or import errors that occur before the application's own SDK setup, install the SDK and run the script through the wrapper:

```bash
export TRACELENS_PROJECT_ID=your-project-id
export TRACELENS_API_URL=http://127.0.0.1:8000
python -m tracelens_sdk.cli path/to/your_rag_app.py

# Alternatively, when the console script is permitted by your OS
tracelens-run path/to/your_rag_app.py
```

On PowerShell, set the same values with `$env:TRACELENS_PROJECT_ID` and `$env:TRACELENS_API_URL`. The wrapper uses best-effort telemetry and re-raises application errors so the process still exits unsuccessfully when the script fails. A reachable backend is required to persist the startup failure.
