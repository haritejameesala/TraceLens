# TraceLens — RAG Observability & Diagnostics

TraceLens is a RAG observability and diagnostic platform designed to help developers understand what happens inside Retrieval-Augmented Generation (RAG) applications.

RAG pipelines can fail silently. A model may return an answer even when retrieval produces no useful documents, a dependency may fail, or response quality may degrade between runs. TraceLens collects execution telemetry, provides run timelines, compares historical executions, and helps developers investigate failures using structured evidence.

This repository contains the TraceLens dashboard, backend API, Python SDK, and a sample customer-support RAG application.

> **Local demo configuration:** This version is configured for simple local development without requiring users to sign in. Do not expose the no-login configuration directly to the public internet. Enable appropriate authentication and authorization before deploying a shared instance.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [1. Clone or Extract the Project](#1-clone-or-extract-the-project)
- [2. Start MongoDB](#2-start-mongodb)
- [3. Configure the Backend](#3-configure-the-backend)
- [4. Install and Start the Backend](#4-install-and-start-the-backend)
- [5. Install and Start the Frontend](#5-install-and-start-the-frontend)
- [6. Configure the RAG Demo](#6-configure-the-rag-demo)
- [7. Install the TraceLens SDK](#7-install-the-tracelens-sdk)
- [8. Start Ollama](#8-start-ollama)
- [9. Run the RAG Application](#9-run-the-rag-application)
- [10. Verify TraceLens](#10-verify-tracelens)
- [Environment Variables](#environment-variables)
- [SDK Integration](#sdk-integration)
- [API Endpoints](#api-endpoints)
- [Troubleshooting](#troubleshooting)
- [Security and Deployment](#security-and-deployment)
- [Limitations](#limitations)

---

## Features

### 1. RAG execution observability

- Track application runs.
- Record lifecycle events and execution stages.
- Inspect event timelines.
- Capture supported LangChain operations through SDK callbacks.
- Record execution metadata, durations, counts, and failure information.

### 2. Run comparison

Compare executions to investigate changes in:

- Execution status.
- Event sequences.
- Retrieval activity.
- Errors and execution behavior.

### 3. Diagnostic investigations

TraceLens provides structured diagnostic findings to help developers investigate issues such as failed runs, missing retrieval results, and suspicious execution behavior.

Diagnostic results are investigative aids. They should not be treated as proof of a root cause without supporting evidence.

### 4. Project management

Organize observed applications into projects and associate telemetry with the relevant project.

The local demo is intended for one developer or a trusted local environment. Project selection alone is not a substitute for user authorization or tenant isolation.

### 5. Python SDK

The SDK provides:

- Run lifecycle tracking.
- Event recording.
- Step-level instrumentation helpers.
- LangChain callback integration.
- Best-effort telemetry delivery.
- Exception and execution-failure reporting.

### 6. Customer-support RAG example

The included sample application demonstrates a RAG pipeline using LangChain, Chroma, Sentence Transformers, and Ollama.

It uses local model inference and a sample knowledge base to demonstrate telemetry collection without requiring a hosted LLM API key.

---

## Architecture

```text
                 Developer
                     |
                     v
          +----------------------+
          | TraceLens Frontend   |
          | React + TypeScript   |
          +----------+-----------+
                     |
                HTTP / JSON
                     |
                     v
          +----------------------+
          | TraceLens Backend    |
          | FastAPI              |
          | Projects / Runs      |
          | Events / Findings    |
          +----------+-----------+
                     |
                     v
          +----------------------+
          | MongoDB              |
          | Projects / Telemetry |
          | Diagnostic Records   |
          +----------------------+

          Observed RAG Application
                     |
                     v
          +----------------------+
          | TraceLens Python SDK |
          | Run / Event Tracking |
          | LangChain Callbacks  |
          +----------+-----------+
                     |
                HTTP / JSON
                     |
                     v
               FastAPI Backend

          Sample RAG Application
                     |
                     v
          +----------------------+
          | LangChain            |
          | Chroma Retrieval     |
          | Sentence Transformers|
          | Ollama LLM           |
          +----------------------+
```

### Technology stack

| Component | Technology |
|---|---|
| Frontend | React, TypeScript, Vite |
| Backend | Python, FastAPI |
| Database | MongoDB |
| SDK | Python, HTTPX |
| RAG framework | LangChain |
| Vector database | Chroma |
| Embeddings | Sentence Transformers |
| Local LLM | Ollama |
| API communication | HTTP and JSON |

---

## Repository Structure

```text
TraceLens/
├── README.md
├── docker-compose.yml
├── .env.example
│
├── tracelens-frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── styles.css
│   │   └── date.ts
│   ├── package.json
│   └── vite.config.ts
│
├── tracelens-backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── auth.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── serialization.py
│   │   ├── diagnostics.py
│   │   ├── investigation.py
│   │   ├── memory.py
│   │   └── agent_tools.py
│   ├── requirements.txt
│   ├── .env.example
│   └── tests/
│
├── tracelens-sdk/
│   ├── tracelens_sdk/
│   │   ├── client.py
│   │   ├── events.py
│   │   ├── integrations.py
│   │   ├── decorators.py
│   │   ├── privacy.py
│   │   └── cli.py
│   ├── examples/
│   ├── docs/
│   ├── tests/
│   └── pyproject.toml
│
└── rag-customer-support/
    ├── main.py
    ├── requirements.txt
    ├── .env.example
    ├── knowledge_base/
    └── tests/
```

---

## Prerequisites

Install the following software before starting the project.

| Software | Purpose |
|---|---|
| Python 3.10 or 3.11 | Backend, SDK, and RAG application |
| Node.js and npm | Frontend development |
| MongoDB  | Persistent storage |
| Ollama | Local LLM inference for the sample RAG application |
| Git | Optional source-code version control |

Check your installations:

```powershell
python --version
node --version
npm --version
docker --version
ollama --version
```

Docker is optional if MongoDB is already installed and running locally.

---

## 1. Clone or Extract the Project

If you have the project ZIP, extract it into a convenient directory.

For example:

```text
D:\other_than_downloads\TraceLens
```

Open PowerShell and move to the project root:

```powershell
cd "D:\other_than_downloads\TraceLens"
```

All commands below assume this directory structure.

---

## 2. Start MongoDB

TraceLens uses MongoDB to store project and execution telemetry.

### Option A: Start MongoDB with Docker

From the project root, run:

```powershell
docker compose up -d mongodb
```

Check the container:

```powershell
docker ps
```

The supplied Compose configuration exposes MongoDB on port `27017` and stores its data in a named Docker volume.

### Option B: Use an existing local MongoDB installation

Ensure the MongoDB service is running and accessible at:

```text
mongodb://localhost:27017
```

Test the port:

```powershell
Test-NetConnection 127.0.0.1 -Port 27017
```

A successful TCP connection confirms that the port is reachable. The backend's own readiness check is the stronger confirmation that MongoDB authentication, configuration, and database communication are working.

---

## 3. Configure the Backend

Open:

```text
tracelens-backend/.env.example
```

Copy it to:

```text
tracelens-backend/.env
```

Using PowerShell:

```powershell
cd "D:\other_than_downloads\TraceLens\tracelens-backend"
Copy-Item .env.example .env
```

Edit `.env` and verify the following settings:

```dotenv
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=tracelens

RCA_PROVIDER=ollama
RCA_OLLAMA_BASE_URL=http://127.0.0.1:11434
RCA_OLLAMA_MODEL=qwen2.5:3b
RCA_TIMEOUT_SECONDS=45

AUTH_SECRET=replace-with-a-random-secret-at-least-32-characters
FRONTEND_URL=http://127.0.0.1:5173
```

Generate a random secret in PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Replace the example `AUTH_SECRET` with the generated value.

Do not commit `.env` to version control.

The local demo is intended to avoid requiring users to sign in. Verify the authentication behavior in the actual checked-out backend before assuming a particular environment variable disables every authentication check.

---

## 4. Install and Start the Backend

Open a PowerShell terminal:

```powershell
cd "D:\other_than_downloads\TraceLens\tracelens-backend"

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Start FastAPI:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Keep this terminal open.

### Verify the backend

Open these URLs in your browser:

- Health check: `http://127.0.0.1:8000/health`
- Interactive API documentation: `http://127.0.0.1:8000/docs`

The backend should report healthy status only when its readiness checks pass.

If the backend cannot connect to MongoDB, inspect its terminal output before proceeding.

---

## 5. Install and Start the Frontend

Open a second PowerShell terminal:

```powershell
cd "D:\other_than_downloads\TraceLens\tracelens-frontend"

npm install
npm run dev
```

Open:

`http://127.0.0.1:5173`

The frontend communicates with the backend. Both services must be running for live project and telemetry data to appear.

### Build the frontend

To check the production build locally:

```powershell
npm run build
```

To run the frontend's available tests:

```powershell
npm test
```

A successful development-server startup is not the same as a successful production build. Run the build command to check TypeScript and bundling errors.

---

## 6. Configure the RAG Demo

Open another PowerShell terminal:

```powershell
cd "D:\other_than_downloads\TraceLens\rag-customer-support"
```

Create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Create the environment file:

```powershell
Copy-Item .env.example .env
```

Configure `rag-customer-support/.env`:

```dotenv
TRACELENS_PROJECT_ID=
TRACELENS_API_KEY=
TRACELENS_API_URL=http://127.0.0.1:8000
TRACELENS_STRICT=false

OLLAMA_MODEL=qwen2.5:3b
OLLAMA_BASE_URL=http://127.0.0.1:11434

CHROMA_PATH=./.chroma
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RETRIEVAL_K=4

APP_VERSION=1.0.0
APP_ENV=local
```

### Project ID and SDK key

The correct values depend on the API-key behavior in your checked-out backend.

If your backend requires SDK keys, create a project in the dashboard and generate the corresponding SDK key. Put the project ID and key in the RAG application's `.env`.

If your local demo uses an unauthenticated ingestion configuration, do not invent an SDK key or use `AUTH_SECRET` as the SDK key. Configure the SDK and backend according to their actual implementation.

Never commit real API keys to source control.

---

## 7. Install the TraceLens SDK

The SDK is maintained as a local Python package inside this repository.

From the RAG application's virtual environment, install it in editable mode:

```powershell
cd "D:\other_than_downloads\TraceLens\tracelens-sdk"

python -m pip install -e ".[langchain]"
```

Return to the RAG application:

```powershell
cd "..\rag-customer-support"
```

Install its dependencies:

```powershell
python -m pip install -r requirements.txt
```

The editable installation means changes to the local SDK source can be used without repeatedly rebuilding a wheel.

---

## 8. Start Ollama

Install Ollama from:

`https://ollama.com/`

Pull the model configured in your `.env`:

```powershell
ollama pull qwen2.5:3b
```

Check the local model list:

```powershell
ollama list
```

If Ollama is not already running as a service, start it in a separate terminal:

```powershell
ollama serve
```

The configured local API URL is:

```text
http://127.0.0.1:11434
```

You can test whether the Ollama API is reachable with:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

Use the exact same model name in your `.env` as the model you pulled.

---

## 9. Run the RAG Application

Ensure that:

- MongoDB is running.
- The TraceLens backend is running.
- The frontend is running if you want to inspect the dashboard.
- Ollama is available if the RAG application uses local generation.
- The SDK and RAG dependencies are installed.
- The project ID and SDK key are correct for your backend's configuration.

From the RAG application's directory, run:

```powershell
cd "D:\other_than_downloads\TraceLens\rag-customer-support"

.\.venv\Scripts\Activate.ps1

python main.py
```

If you want to use the SDK's CLI wrapper for startup-failure reporting, use:

```powershell
python -m tracelens_sdk.cli .\main.py
```

Do not add a trailing backslash after `main.py`.

On its first run, the RAG application may download the embedding model and build a local Chroma index. This can take time depending on your internet connection and machine.

Subsequent runs reuse the local index and update it as the knowledge-base content changes.

---

## 10. Verify TraceLens

Use the following checklist.

### Backend

- [ ] MongoDB is reachable.
- [ ] FastAPI starts without a traceback.
- [ ] `http://127.0.0.1:8000/health` responds successfully.
- [ ] `http://127.0.0.1:8000/docs` loads.

### Frontend

- [ ] The Vite development server starts.
- [ ] The dashboard opens at `http://127.0.0.1:5173`.
- [ ] The API connection indicator is healthy.
- [ ] Project data loads from the backend.
- [ ] No repeated authentication errors appear in the backend terminal.

### RAG application

Try questions such as:

- `How do I handle a failed payment?`
- `What should support do if a customer requests data deletion?`
- `What exact discount will I receive next year?`

The final question tests how the RAG system behaves when the supplied knowledge base may not contain the answer.

After submitting queries, inspect the dashboard for new runs and events.

Expected telemetry depends on which LangChain operations the SDK observes and whether delivery succeeds.

### Compare runs

Run the same query more than once or compare queries with different retrieval behavior. Use the comparison view to inspect execution changes.

A retrieved-document count is not the same as semantic relevance. To measure relevance reliably, use an appropriate evaluator or labeled test dataset.

---

## Environment Variables

### Backend

| Variable | Purpose |
|---|---|
| `MONGODB_URI` | MongoDB connection URI |
| `MONGODB_DATABASE` | Database name |
| `MONGODB_TLS_CA_FILE` | Optional custom TLS CA bundle |
| `RCA_PROVIDER` | Provider used for root-cause investigations |
| `RCA_OLLAMA_BASE_URL` | Ollama API URL for diagnostics |
| `RCA_OLLAMA_MODEL` | Local model used for investigations |
| `RCA_TIMEOUT_SECONDS` | Investigation model timeout |
| `AUTH_SECRET` | Secret used by account-token signing where enabled |
| `FRONTEND_URL` | Frontend origin used by backend configuration |

### RAG application

| Variable | Purpose |
|---|---|
| `TRACELENS_PROJECT_ID` | Project associated with telemetry |
| `TRACELENS_API_KEY` | SDK ingestion key when required |
| `TRACELENS_API_URL` | TraceLens backend URL |
| `TRACELENS_STRICT` | Whether telemetry delivery failures should interrupt the application |
| `OLLAMA_MODEL` | Model used by the RAG application |
| `OLLAMA_BASE_URL` | Local Ollama API URL |
| `CHROMA_PATH` | Local persistent vector-store directory |
| `EMBEDDING_MODEL` | Sentence Transformers embedding model |
| `RETRIEVAL_K` | Number of documents requested from retrieval |
| `APP_VERSION` | RAG application version metadata |
| `APP_ENV` | Application environment metadata |

---

## SDK Integration

TraceLens is designed to observe RAG execution through its Python SDK.

### Automatic LangChain callback integration

For supported LangChain operations, the SDK can collect callback events without requiring manual instrumentation around every individual framework call.

For custom applications, install the SDK and use its callback integration.

Example:

```python
from tracelens_sdk import TraceLens, langchain_callback

project_id = "your-project-id"
api_url = "http://127.0.0.1:8000"

with TraceLens(
    project_id=project_id,
    api_url=api_url,
    strict=False,
) as tracer:
    callback = langchain_callback(
        tracer,
        run_name="support-rag",
        version="1.0.0",
    )

    answer = chain.invoke(
        {"question": "How do I handle a failed payment?"},
        config={"callbacks": [callback]},
    )
```

Replace `chain` with your actual LangChain chain and configure the correct project and API settings.

This example demonstrates the callback pattern. It is not a complete runnable application without a defined chain and valid backend configuration.

### Custom instrumentation

When a framework callback does not expose enough application-specific detail, use the SDK's run and event helpers.

Refer to:

- `tracelens-sdk/README.md`
- `tracelens-sdk/docs/API.md`
- `tracelens-sdk/docs/SECURITY.md`
- `tracelens-sdk/examples/custom_rag.py`

### Delivery behavior

With `TRACELENS_STRICT=false`, telemetry delivery failures are intended to be handled in best-effort mode so that the application can continue.

Best-effort delivery means some telemetry may be lost when the backend is unavailable or rejects requests.

It does not mean that failed ingestion has been repaired automatically.

---

## API Endpoints

The backend exposes HTTP endpoints for health checks, projects, runs, events, comparisons, findings, and investigations.

Common endpoints include:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Check backend readiness |
| `GET` | `/api/projects` | List projects |
| `POST` | `/api/projects` | Create a project |
| `GET` | `/api/projects/{project_id}/runs` | List runs for a project |
| `POST` | `/api/runs` | Ingest a run |
| `GET` | `/api/runs/{run_id}` | Retrieve run details |
| `PATCH` | `/api/runs/{run_id}` | Update run information |
| `POST` | `/api/runs/{run_id}/events` | Ingest an event |
| `GET` | `/api/runs/{run_id}/events` | Retrieve run events |
| `POST` | `/api/runs/compare` | Compare runs |
| `GET` | `/api/runs/{run_id}/findings` | Retrieve diagnostic findings |
| `POST` | `/api/runs/{run_id}/investigate` | Start an investigation |
| `GET` | `/api/projects/{project_id}/memories` | Retrieve project-scoped incident memories |

