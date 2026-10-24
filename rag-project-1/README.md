# RAG Project 1 — TF-IDF baseline

This demo compares a simple TF-IDF retriever across a healthy baseline and a deliberately broken retrieval run. TraceLens records retrieval counts, chunk IDs, generation mode, answer support, and run status so the dashboard can compare the runs.

## Run

Start MongoDB and the TraceLens API first. From the repository root:

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r tracelens-backend/requirements.txt
    python -m pip install -e ./tracelens-sdk
    python -m pip install -r rag-project-1/requirements.txt
    python rag-project-1/main.py

Optional environment variables:
- TRACELENS_API_URL — defaults to http://127.0.0.1:8000
- TRACELENS_API_KEY — must match the backend's optional key
- LLM_API_KEY — enables OpenAI-compatible grounded generation
- LLM_BASE_URL — defaults to https://api.openai.com/v1
- LLM_MODEL — defaults to gpt-4o-mini

Without an LLM key, the demo explicitly prints retrieved evidence only. The second run deliberately returns no chunks to exercise TraceLens regression diagnostics.
