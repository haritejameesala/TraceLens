# RAG Project 2 — ChromaDB semantic retrieval

This demo uses SentenceTransformers embeddings and a persistent ChromaDB collection. It compares a healthy baseline with a deliberately broken retrieval run and sends chunk counts and distances to TraceLens.

## Run

Start MongoDB and the TraceLens API first. From the repository root:

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r tracelens-backend/requirements.txt
    python -m pip install -e ./tracelens-sdk
    python -m pip install -r rag-project-2/requirements.txt
    python rag-project-2/main.py

The first run downloads the all-MiniLM-L6-v2 embedding model. Chroma data is persisted under CHROMA_PATH, which defaults to ./chroma_db relative to the current working directory.

Optional environment variables:
- TRACELENS_API_URL — defaults to http://127.0.0.1:8000
- TRACELENS_API_KEY — must match the backend's optional key
- CHROMA_PATH — local persistent vector-store directory
- LLM_API_KEY — enables OpenAI-compatible grounded generation
- LLM_BASE_URL — defaults to https://api.openai.com/v1
- LLM_MODEL — defaults to gpt-4o-mini

Without an LLM key, the demo explicitly prints retrieved evidence only. The second run deliberately returns no chunks to exercise TraceLens regression diagnostics.
