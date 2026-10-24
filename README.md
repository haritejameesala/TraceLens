# TraceLens

**RAG observability, diagnostics, and evidence-backed root-cause
analysis.**

TraceLens helps developers understand what happened during a
retrieval-augmented generation (RAG) execution, investigate failures,
and compare a problematic run with previous runs from the same project.

It combines a Python SDK, a FastAPI backend, MongoDB persistence, and a
React + TypeScript dashboard. Where telemetry is available,
investigations can compare pipeline stages and configuration values
across historical runs to highlight changes associated with a failure.

> **Project status:** TraceLens is an actively developed project.
> Validate the full SDK → backend → database → dashboard workflow in
> your environment before relying on it in production.

---

## Contents

- [Why TraceLens?](#why-tracelens)
- [Features](#features)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Configure the backend](#configure-the-backend)
- [Run the frontend](#run-the-frontend)
- [Install and use the SDK](#install-and-use-the-sdk)
- [Run the RAG example](#run-the-rag-example)
- [Test a failure and investigate
  it](#test-a-failure-and-investigate-it)
- [How investigations work](#how-investigations-work)
- [Development and tests](#development-and-tests)
- [Security and privacy](#security-and-privacy)
- [Troubleshooting](#troubleshooting)
- [Roadmap ideas](#roadmap-ideas)
- [Contributing](#contributing)
- [License](#license)

## Why TraceLens?

RAG failures are often difficult to diagnose from a final answer or a
single exception. The problem may arise during retrieval, prompt
construction, model invocation, configuration, or a dependency call.

TraceLens records run and event telemetry, keeps a history of
executions, and helps answer:

1.  **What failed?** Identify the first recorded failure and its
    surrounding events.
2.  **What changed?** Compare relevant stages and recorded configuration
    with successful historical runs.
3.  **What evidence supports the diagnosis?** Link findings to actual
    event records and clearly separate observations from hypotheses.
4.  **What should I check next?** Present focused troubleshooting
    actions based on the available evidence.

TraceLens is an observability and diagnostic tool---not a guarantee that
every root cause can be determined from incomplete telemetry.

## Features

- **Run and event history** for instrumented RAG applications.
- **Python SDK** for sending execution data to the TraceLens backend.
- **Framework integration hooks** for supported LangChain flows, plus
  manual instrumentation options.
- **Historical comparisons** that can compare matching pipeline stages
  and recorded configuration fields.
- **Evidence-aware investigations** that distinguish recorded facts
  from inferred explanations.
- **Deterministic fallback diagnostics** when the configured RCA model
  is unavailable.
- **AI-assisted investigation** through a locally hosted Ollama model
  when configured and reachable.
- **Dashboard actions** for managing projects and runs, copying
  project IDs, and exporting available event data.
- **Privacy controls** intended to reduce sensitive data collection;
  applications should still review what they transmit.

Feature availability depends on the version you are running and the
telemetry captured by the SDK.

## Architecture

```text
Instrumented RAG application
          |
          v
      TraceLens SDK
          |
          | HTTP events / run metadata
          v
     FastAPI backend ---------> MongoDB
          |
          | investigation context
          v
  Diagnostics + historical comparison
          |
          +----> Ollama RCA model (optional)
          |
          v
    React + TypeScript dashboard
```

### Main components

---

Component Responsibility

---

`tracelens-sdk` Python client, event
instrumentation, privacy helpers,
and integrations

`tracelens-backend` FastAPI API, persistence access,
diagnostics, historical comparison,
and investigation orchestration

`tracelens-frontend` Dashboard for projects, runs,
events, and investigation reports

`rag-customer-support` Example customer-support RAG
application used for local
integration and failure testing

---

## Repository layout

```text
TraceLens/
├── tracelens-sdk/             # Python SDK
│   ├── tracelens_sdk/
│   ├── tests/
│   ├── docs/
│   └── examples/
├── tracelens-backend/         # FastAPI service
│   ├── app/
│   └── tests/
├── tracelens-frontend/        # React + TypeScript + Vite
│   └── src/
├── rag-customer-support/      # Example RAG application
│   ├── knowledge_base/
│   └── tests/
├── docker-compose.yml         # Local infrastructure, if configured
├── .env.example
└── .gitignore
```

Your checkout may include additional RAG examples or files. Use the
paths present in your local repository if they differ from this layout.

## Requirements

- Python 3.10 or newer (use the version supported by the package
  metadata in your checkout)
- Node.js and npm
- Docker Desktop, if using the provided Compose setup for MongoDB
- MongoDB
- Ollama and a locally available model for AI-assisted RCA (optional;
  deterministic diagnostics should remain useful without it)

Commands below use Windows PowerShell. Run each long-running service in
a separate terminal and leave it open.

## Quick start

### 1. Open the repository

```powershell
cd "D:\other_than_downloads\TraceLens"
```

### 2. Start MongoDB

If the `tracelens-mongodb` container already exists:

```powershell
docker start tracelens-mongodb
```

Otherwise, if the repository's Compose file defines MongoDB:

```powershell
docker compose up -d
```

Check the container:

```powershell
docker ps
```

### 3. Configure and start the backend

Open a new PowerShell terminal:

```powershell
cd "D:\other_than_downloads\TraceLens\tracelens-backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create `.env` from `.env.example` if needed, then edit the settings as
described below. Start the API:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API should be available at `http://127.0.0.1:8000`. If enabled by
the application, interactive API documentation is available at
`http://127.0.0.1:8000/docs`.

### 4. Start the frontend

Open another PowerShell terminal:

```powershell
cd "D:\other_than_downloads\TraceLens\tracelens-frontend"
npm install
npm run dev
```

Open the local URL printed by Vite, commonly `http://127.0.0.1:5173`.

## Configure the backend

Keep local configuration in `.env`, not in committed source files. A
typical local configuration is:

```dotenv
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=TRACELENSDB

RCA_PROVIDER=ollama
RCA_OLLAMA_BASE_URL=http://127.0.0.1:11434
RCA_OLLAMA_MODEL=qwen2.5:1.5b
RCA_TIMEOUT_SECONDS=45
```

These are example values based on a local development setup. Check
`tracelens-backend/.env.example` and `tracelens-backend/app/config.py`
for the exact variables supported by your checkout.

Important:

- Keep the database name consistent if you want to inspect existing
  history.
- `RCA_OLLAMA_BASE_URL` is the backend's investigation-model endpoint.
- The RAG application's `OLLAMA_BASE_URL` is separate. Changing the
  RAG endpoint to test a failure should not accidentally change the
  backend RCA endpoint.
- Restart the backend after changing environment variables.

To check a local Ollama installation:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

If the configured model is not installed, pull it using the model name
configured for your environment:

```powershell
ollama pull qwen2.5:1.5b
```

## Install and use the SDK

Activate the virtual environment used by your RAG application, then
install the local SDK in editable mode:

```powershell
cd "D:\other_than_downloads\TraceLens\rag-customer-support"
.\.venv\Scripts\Activate.ps1
python -m pip install -e "D:\other_than_downloads\TraceLens\tracelens-sdk"
```

Adjust the path if your checkout is elsewhere. Confirm that the package
imports:

```powershell
python -c "import tracelens_sdk; print('TraceLens SDK import successful')"
```

Configure the RAG application using its `.env.example` as the source of
truth. Common settings include:

```dotenv
TRACELENS_API_URL=http://127.0.0.1:8000
TRACELENS_PROJECT_ID=your-existing-project-id
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

Use a real project ID created in your TraceLens instance. Do not commit
a real `.env` file or credentials.

### Instrumentation approach

Use the SDK's supported integration callbacks for framework operations
it can observe. Add explicit instrumentation around custom retrieval,
preprocessing, prompt-building, and application-specific steps when
those steps are not captured automatically.

Automatic instrumentation is limited to the supported integrations and
the events they can observe; it does not automatically trace arbitrary
code.

For exact signatures and supported options, see:

- [`tracelens-sdk/README.md`](tracelens-sdk/README.md)
- [`tracelens-sdk/docs/API.md`](tracelens-sdk/docs/API.md)
- [`tracelens-sdk/examples/custom_rag.py`](tracelens-sdk/examples/custom_rag.py)

## Run the RAG example

With the backend and frontend running, open a separate terminal:

```powershell
cd "D:\other_than_downloads\TraceLens\rag-customer-support"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e "..\tracelens-sdk"
```

If your RAG application uses additional dependencies or has a separate
setup guide, follow its local README and requirements file. Configure
its `.env` and start it using the entry point present in your checkout,
for example:

```powershell
python main.py
```

## Test a failure and investigate it

A useful development check is to compare a successful generation with a
deliberately failing generation.

1.  Confirm Ollama is reachable at the intended working endpoint,
    commonly `http://127.0.0.1:11434`.
2.  Run a successful query and confirm that the run and its events
    appear in TraceLens.
3.  Change only the RAG application's `OLLAMA_BASE_URL` to an endpoint
    where no service is listening, for example `http://127.0.0.1:11435`.
4.  Restart the RAG process so it loads the changed environment.
5.  Run the same query again and open the failed run's investigation.
6.  Confirm that the report identifies the connection-refused error and
    compares the failed generation event with a successful historical
    generation event.

For a useful comparison, both runs must belong to the same project and
record comparable stage/configuration telemetry. If an older run did not
record an endpoint, TraceLens should report that evidence gap rather
than inventing a value.

Restore the working endpoint after the test.

## How investigations work

A TraceLens investigation should:

1.  Load the current run and its recorded events.
2.  Identify the first observed failure and the surrounding event
    sequence.
3.  Retrieve relevant historical runs, prioritizing comparable
    successful executions from the same project.
4.  Compare equivalent pipeline stages and fields that were actually
    recorded.
5.  Construct an evidence-backed diagnostic context.
6.  Use the configured RCA model when available, with deterministic
    diagnostics as a fallback.
7.  Present observations, likely causes, supporting evidence,
    uncertainty, and recommended actions separately.

### Interpreting results

- **Observed fact:** directly supported by a recorded event or field.
- **Likely cause:** an explanation supported by the observed failure
  and relevant historical differences, but not necessarily proven.
- **Alternative explanation:** another plausible cause that the
  current evidence cannot rule out.
- **Missing telemetry:** information that was not recorded and
  therefore cannot be verified.

A timestamp ordering or a difference between two runs is evidence for
investigation, not proof of causation by itself.

## Development and tests

### Backend tests

```powershell
cd "D:\other_than_downloads\TraceLens\tracelens-backend"
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest
```

### SDK tests

```powershell
cd "D:\other_than_downloads\TraceLens\tracelens-sdk"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
```

If the SDK's development extras are not defined in your checkout,
install the test dependencies listed in its `pyproject.toml`. Some
integration tests may require optional framework dependencies.

### Customer-support RAG tests

```powershell
cd "D:\other_than_downloads\TraceLens\rag-customer-support"
.\.venv\Scripts\Activate.ps1
python -m pytest
```

### Frontend checks

```powershell
cd "D:\other_than_downloads\TraceLens\tracelens-frontend"
npm install
npm run build
```

Run the commands in your current checkout and treat their output as the
source of truth; test results can vary with dependency versions and
environment configuration.

## Security and privacy

Trace data may contain prompts, user queries, retrieved text, model
outputs, identifiers, endpoint details, and exception messages. Treat
traces as potentially sensitive.

- Never commit `.env` files, API keys, passwords, certificates, or
  production connection strings.
- Commit `.env.example` files only when they contain safe
  placeholders.
- Review the SDK's privacy/redaction behavior before enabling it on
  real workloads.
- Avoid capturing raw prompts, answers, or retrieved documents unless
  needed and approved.
- Sanitize endpoint credentials and query parameters before recording
  configuration.
- Restrict access to the backend, database, and dashboard in shared
  environments.
- Define retention and deletion policies for runs, events, and
  investigation records.
- Do not expose the development server directly to the public internet
  without authentication, authorization, TLS, and appropriate
  deployment hardening.

See [`tracelens-sdk/docs/SECURITY.md`](tracelens-sdk/docs/SECURITY.md)
for SDK-specific notes.

## Troubleshooting

### Backend cannot connect to MongoDB

- Verify that the MongoDB container or service is running.
- Check `MONGODB_URI` and `MONGODB_DATABASE`.
- Confirm that the backend loaded the intended `.env`.
- Inspect the backend terminal for the full exception.

### AI investigation reports that Ollama is unavailable

- Check that Ollama is running and the configured model is installed.
- Verify `RCA_OLLAMA_BASE_URL` in the backend configuration.
- Restart the backend after environment changes.
- Remember that the RAG model endpoint and the RCA model endpoint are
  separate settings.

### Historical comparison does not show an endpoint difference

- Confirm that the successful and failed runs belong to the same
  project.
- Inspect the actual stored events and metadata for both runs.
- Confirm that comparable generation events recorded the endpoint
  field.
- If older telemetry lacks the field, generate a new baseline after
  enabling the updated instrumentation.

### The reconstructed timeline is empty

The timeline can only show events that were successfully recorded.
Verify that the SDK sent the expected events, that the backend accepted
them, and that they were stored for the run.

### Git reports `LF will be replaced by CRLF`

This is a line-ending warning on Windows, not necessarily a failed
operation. Use a consistent `.gitattributes` policy if the team needs
predictable line endings across operating systems.

### Git reports an `fsync` or object-write error

Do not delete files inside `.git`. Check `git status`, disk space,
concurrent Git processes, filesystem health, and security software
before attempting repository repair.

## Roadmap ideas

Potential areas for continued development include:

- More automatic instrumentation for common RAG frameworks.
- Better span relationships and timeline visualization.
- More robust configuration fingerprints and stage-aware historical
  matching.
- Investigation-quality regression tests using known failure
  scenarios.
- Configurable data retention and richer privacy controls.
- Authentication, authorization, and production deployment hardening.
- Exportable investigation reports and trace bundles.

These are development ideas, not a claim that every item is currently
implemented.

## Contributing

Contributions are welcome. A useful contribution should include:

1.  A clear description of the problem or proposed change.
2.  Tests covering new behavior and relevant failure cases.
3.  Updated documentation for public SDK or API changes.
4.  No secrets, local environment files, generated dependencies, or
    production data.
5.  A note describing any compatibility or telemetry-schema changes.

Before submitting changes, run the relevant backend, SDK, and frontend
checks described above.

## License

Add the project's chosen license before publishing or distributing
TraceLens. Until a license is included in the repository, do not assume
that others have permission to reuse, modify, or redistribute the code.
