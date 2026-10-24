# TraceLens

TraceLens is a developer tool for observing and debugging retrieval-augmented generation (RAG) applications. A Python SDK captures execution traces; FastAPI persists runs and events in MongoDB; a browser dashboard compares runs; project-scoped knowledge retrieval supplies evidence for diagnostics.

## Included capabilities

- Python tracing SDK with run/step contexts, timing, error capture, API-key support, and recursive redaction of common sensitive fields.
- FastAPI endpoints for projects, runs, events, run comparisons, findings, knowledge ingestion, lexical retrieval, and diagnoses.
- MongoDB indexes for trace data, knowledge chunks, and saved diagnoses.
- Browser dashboard for run inspection, comparison, document ingestion, retrieval search, and diagnosis.
- Optional OpenAI-compatible chat-completions integration. Without a key, the API explicitly returns evidence-only results rather than pretending it generated a diagnosis.
- Existing TF-IDF and ChromaDB/SentenceTransformers examples remain available.

## Quick start (Windows PowerShell)

Prerequisites: Python 3.10+, MongoDB 6+ (local or Docker Desktop), and optionally an OpenAI-compatible API key.

1. From the repository root, start MongoDB:

       docker compose up -d mongodb

2. Configure and start the API:

       cd tracelens-backend
       py -m venv .venv
       .\.venv\Scripts\Activate.ps1
       python -m pip install -r requirements.txt
       Copy-Item .env.example .env
       uvicorn app.main:app --reload

3. Open http://127.0.0.1:8000. API docs are at http://127.0.0.1:8000/docs.

4. Optional LLM setup: set LLM_API_KEY and LLM_MODEL in tracelens-backend/.env. LLM_BASE_URL accepts an OpenAI-compatible API base URL. Restart the backend after changing values.

5. Optional API protection: set TRACELENS_API_KEY to a strong random value. The dashboard asks for this key, and SDK clients send it in the X-API-Key header. Do not expose the API publicly without authentication, TLS, rate limiting, and per-project authorization.

## Try the prebuilt demo

After the backend is running, open a second terminal at the repository root and run:

    python -m pip install httpx
    python scripts/demo_seed.py

The script creates a separate demo project, ingests a runbook, records a healthy baseline and a deliberately broken retrieval run, compares them, and saves a diagnosis. It never overwrites existing projects. Refresh the dashboard and select “TraceLens Demo — RAG regression”. Re-running the script creates another fresh demo workspace.

## Instrument a Python application

Install the SDK in your application's virtual environment:

    pip install -e ./tracelens-sdk

Create a project in the dashboard and copy its project ID. Then:

    import os
    from tracelens_sdk import TraceLens

    with TraceLens(project_id=os.environ["TRACELENS_PROJECT_ID"],
                   api_url=os.getenv("TRACELENS_API_URL", "http://127.0.0.1:8000"),
                   api_key=os.getenv("TRACELENS_API_KEY") or None, strict=False) as tracer:
        with tracer.start_run("support-answer", version="v1") as run:
            with run.trace_step("retrieve_documents", event_type="retrieval",
                                payload={"query": "password policy"}):
                # Record relevant_chunk_count, chunk IDs, scores, and index version.
                pass

strict=False prevents telemetry transport failures from interrupting the host application. Explicitly choose what to record; avoid sending raw conversations, credentials, or private data in trace payloads.

## Knowledge and RAG workflow

1. Select a project in the dashboard.
2. Add a runbook, troubleshooting guide, or evaluation note under Knowledge.
3. Search project knowledge to see ranked chunks and source metadata.
4. Ask a diagnostic question. Optionally attach a run ID so the configured LLM receives trace evidence alongside retrieved documents.
5. Review citations, source chunks, and the distinction between observed facts and hypotheses.

The built-in retriever is a dependency-free lexical baseline. The separate ChromaDB example demonstrates embedding-based retrieval. Evaluate both on a fixed question set before choosing a production retriever.

## Tests

From tracelens-backend, run:

    python -m pytest -q

A GitHub Actions workflow tests Python 3.10–3.12 and checks that the SDK imports. These tests do not replace live MongoDB integration tests or browser end-to-end tests.

## Security notes

- API-key protection is opt-in for local development. Enable it before network exposure.
- The current API key is a single shared development key, not multi-tenant identity. Production needs per-project credentials, authorization on every resource, rate limits, TLS, audit logs, and secret management.
- Redaction is best-effort and key-based. Do not assume arbitrary text is automatically scrubbed.
- Retrieved documents and trace content are untrusted input. Prompt instructions reduce but do not eliminate prompt-injection risk.
- Never commit .env, API keys, user data, model credentials, or real traces.

## Layout

- tracelens-sdk/ — Python SDK
- tracelens-backend/ — FastAPI, MongoDB, retrieval, diagnostics, tests, dashboard
- rag-project-1/ — TF-IDF experiment
- rag-project-2/ — ChromaDB + SentenceTransformers experiment
