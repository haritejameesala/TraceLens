# TraceLens — Start here

TraceLens records instrumented Python/RAG pipeline events through an SDK and FastAPI backend, stores them in MongoDB, compares runs, and generates deterministic evidence-linked findings. It is a historical tracing/diagnosis system, not an interactive debugger with arbitrary breakpoints or variable mutation.

## Structure

- `tracelens-sdk/` — installable SDK (`from tracelens_sdk import TraceLens`)
- `tracelens-backend/` — FastAPI + MongoDB API
- `rag-project-1/` — TF-IDF/scikit-learn RAG demo
- `rag-project-2/` — ChromaDB + SentenceTransformers demo

## Start MongoDB locally

Install Docker Desktop, then from this directory:

```powershell
docker compose up -d mongodb
```

## Start the backend (terminal 1)

```powershell
cd tracelens-backend
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python test_mongo.py
python -m uvicorn app.main:app --reload
```

If using Atlas, edit `tracelens-backend/.env` before testing. Do not commit `.env` or share its URI/password. `/health` verifies database connectivity; Uvicorn startup requires MongoDB to be reachable.

## Run TF-IDF RAG (terminal 2)

```powershell
cd rag-project-1
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e ..	racelens-sdk
python main.py
```

## Run semantic RAG (terminal 3)

```powershell
cd rag-project-2
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e ..	racelens-sdk
python main.py
```

The first semantic run downloads `sentence-transformers/all-MiniLM-L6-v2`. Internet access is needed unless the model is already cached. A Hugging Face token is optional for this public model, though unauthenticated downloads may be rate-limited.

## Demo expectation

Each RAG app creates a project, records a baseline run, records a deliberately regressed run, and requests a comparison. The TF-IDF baseline should retrieve `security-01`; the semantic baseline should retrieve `policy-a`. The intentionally broken filter returns no documents in the regression run. Both are separate from normal retrieval behavior and are included only to demonstrate regression diagnosis.

## Security and limits

- `.env` is ignored by Git. `.env.example` contains local defaults only.
- SDK payloads should contain only safe metadata; avoid secrets and sensitive user content.
- A run marked `success` means the instrumented program completed; retrieval quality is represented separately by retrieval event metrics.
- Diagnostics are deterministic heuristics. They identify suspicious evidence, not guaranteed root causes.
- Verify MongoDB persistence by querying API endpoints and the database; backend startup alone is not proof that a past run was stored.
