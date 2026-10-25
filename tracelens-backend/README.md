# TraceLens

## RAG Observability & Diagnostics --- Project Report

## 1. Overview

**TraceLens** helps developers investigate failures and quality
regressions in Retrieval-Augmented Generation (RAG) applications. It
captures execution traces, stores run history, compares a current run
with previous successful runs, and produces evidence-based diagnostic
reports.

A RAG application typically retrieves documents, builds a prompt, calls
a Large Language Model (LLM), and returns an answer. The request may
technically succeed while retrieval quality drops, latency increases,
the wrong evidence is retrieved, or generation fails. TraceLens makes
recorded pipeline behavior easier to inspect.

**Core value:** show what happened, what changed compared with earlier
executions, what evidence supports a diagnosis, and what the developer
should investigate next.

## 2. Architecture

``` text
Developer's RAG Application
          |
          v
TraceLens Python SDK
  - Run and event capture
  - Supported LangChain callbacks
          |
          | HTTP telemetry
          v
FastAPI Backend <----------> MongoDB
          |                    |
          |                    +-- Projects and runs
          |                    +-- Events and findings
          |                    +-- Investigations
          |                    +-- Incident memories
          |
          +--> Historical run comparison
          |
          +--> Deterministic diagnostics
          |
          +--> Optional Ollama RCA enrichment
          |
          v
React + TypeScript Dashboard
```

The SDK instruments supported operations and sends telemetry to the
backend. FastAPI validates requests, coordinates comparisons and
diagnosis, and persists records in MongoDB. The dashboard calls the
backend API; it does not connect directly to MongoDB.

The included customer-support RAG demo uses **LangChain** to orchestrate
the pipeline, **Chroma** for vector retrieval, and **Ollama** for local
generation. Those components are separate from TraceLens's own telemetry
database.

## 3. Main Components

  -----------------------------------------------------------------------
  Component                           Role
  ----------------------------------- -----------------------------------
  Python SDK                          Starts runs, records events, and
                                      sends telemetry

  LangChain callback integration      Captures supported chain,
                                      retriever, and model lifecycle
                                      events

  FastAPI backend                     Provides APIs, loads history, runs
                                      diagnostics, and stores results

  MongoDB                             Durable store for TraceLens
                                      projects and execution history

  Deterministic diagnostics           Classifies recognizable errors and
                                      compares traces

  Optional Ollama                     Enriches the diagnostic explanation
                                      with natural language

  React + TypeScript                  Dashboard for projects, runs,
                                      events, findings, and
                                      investigations

  Chroma                              Vector retrieval in the example RAG
                                      application

  Docker Compose                      Runs local MongoDB with a
                                      persistent named volume
  -----------------------------------------------------------------------

## 4. End-to-End Workflow

1.  **Run the RAG application.** The application processes a query using
    its retriever and LLM.
2.  **Capture telemetry.** The TraceLens SDK or supported LangChain
    callbacks record the run and available events, statuses, timings,
    errors, and metadata.
3.  **Send telemetry.** The SDK sends run and event data to FastAPI over
    HTTP.
4.  **Persist history.** The backend stores the records in MongoDB.
5.  **Select a run.** The developer opens the dashboard and chooses a
    run to inspect or investigate.
6.  **Load history.** The backend retrieves the current trace and
    relevant runs from the same project.
7.  **Compare and diagnose.** Deterministic logic examines recorded
    errors and compares stages and configuration fields with historical
    executions.
8.  **Optionally enrich.** If configured, Ollama adds a natural-language
    explanation. If enrichment fails, the deterministic report can still
    be used.
9.  **Save the result.** The backend persists the investigation and may
    create an incident-memory record for a failed run.
10. **Review evidence.** The dashboard presents the timeline, findings,
    likely cause, recommendations, and limitations.

## 5. MongoDB: Why We Use It

MongoDB is TraceLens's **operational history database**. It stores
telemetry and diagnostic records; it is not the LLM and not the vector
database.

### Why MongoDB fits this project

-   **Flexible event payloads:** retrieval, chain, and generation events
    may have different fields.
-   **Document-oriented structure:** run metadata, nested payloads, and
    investigation reports fit naturally into documents.
-   **Historical retrieval:** the backend can query project runs, events
    for a run, and memories for a project.
-   **Indexes:** indexes support lookups by IDs, project, run,
    timestamps, and incident signatures.
-   **Local development:** MongoDB can run in Docker Compose, with a
    named volume to preserve database files when the container is
    recreated.

### Why not other storage options?

  -----------------------------------------------------------------------
  Option                              Why it is not the primary store
                                      here
  ----------------------------------- -----------------------------------
  JSON files / ordinary logs          Useful for simple debugging, but
                                      less convenient for indexed,
                                      multi-project queries and updating
                                      structured investigation records

  PostgreSQL                          A valid alternative with strong
                                      relational constraints and SQL
                                      analytics. MongoDB was chosen
                                      because telemetry is naturally
                                      document-oriented and event
                                      payloads vary

  Redis                               Useful for caching, queues, and
                                      transient state; MongoDB is a more
                                      natural primary store for durable
                                      project and run history

  Chroma                              Designed for vector similarity
                                      retrieval in the demo knowledge
                                      base, not as the main store for
                                      TraceLens run/event records
  -----------------------------------------------------------------------

MongoDB is a good fit for the current data model, but it is not
universally better than PostgreSQL. The choice is a trade-off based on
the project's document-shaped telemetry and query patterns.

### MongoDB versus Chroma versus Ollama

-   **MongoDB:** projects, runs, events, findings, investigations,
    incident memories.
-   **Chroma:** vector embeddings and similarity retrieval for the
    example support knowledge base.
-   **Ollama:** runs the configured LLM locally for answer generation
    and, optionally, diagnostic enrichment.

## 6. MongoDB Data Model

TraceLens stores related records in separate collections and links them
using identifiers.

  -----------------------------------------------------------------------
  Collection                          What it stores
  ----------------------------------- -----------------------------------
  `projects`                          Project identity, metadata, and
                                      project key

  `runs`                              One execution: project, scenario,
                                      version, status, timestamps, and
                                      metadata

  `events`                            Individual observations or stages
                                      belonging to a run

  `findings`                          Results from explicit
                                      baseline/current-run comparisons

  `investigations`                    Diagnostic reports and their
                                      evidence, alternatives, and
                                      recommendations

  `incident_memories`                 Compact, project-scoped summaries
                                      of recurring failures and confirmed
                                      fixes
  -----------------------------------------------------------------------

A **run is one execution**. An **event is one recorded operation or
observation inside that execution**. A single run can therefore have
many events.

The backend defines indexes for unique identifiers and common query
patterns, including project run history, events ordered by run and
timestamp, findings by run, investigations by run, and incident memories
by project and signature. These are logical ID-based relationships; they
are not relational foreign-key constraints enforced by MongoDB.


## 7. Core Schemas (Data Shapes)

These schemas summarize the Pydantic request models in `tracelens-backend/app/models.py` and the SDK event model in `tracelens-sdk/tracelens_sdk/events.py`. The JSON examples are illustrative; generated IDs and timestamps will differ at runtime.

### Project schema

A project groups runs from one application.

```json
{
  "project_key": "support-rag-python",
  "name": "Customer Support RAG",
  "description": "Support assistant observability",
  "framework": "python"
}
```

- `project_key`: optional stable key; 3–160 characters and restricted to lowercase letters, digits, `.`, `_`, `:`, and `-` with a valid starting character.
- `name`: required, 1–120 characters.
- `description`: optional, defaults to an empty string, up to 800 characters.
- `framework`: optional, defaults to `python`, up to 80 characters.

The stored project also has a generated `project_id` and creation metadata.

### Run schema

A run represents one application execution.

```json
{
  "project_id": "prj_example",
  "scenario": "customer-support-query",
  "version": "1.0.0",
  "baseline_run_id": null,
  "status": "running",
  "metadata": {
    "environment": "local"
  }
}
```

- `project_id`: project that owns the run.
- `scenario`: required, 1–150 characters.
- `version`: optional, defaults to `dev`, up to 100 characters.
- `baseline_run_id`: optional reference to a comparison baseline.
- `status`: `running`, `success`, or `failed`.
- `metadata`: optional key/value object.

The stored run also has a generated `run_id` and creation information. A run can have many events.

### Event schema

An event is one recorded stage or observation inside a run.

```json
{
  "event_id": "evt_example",
  "step": "generation",
  "event_type": "generation",
  "status": "failed",
  "timestamp": "2026-10-25T10:30:00Z",
  "duration_ms": 45000,
  "payload": {
    "llm_model": "qwen2.5:1.5b",
    "endpoint": "http://127.0.0.1:11434"
  },
  "error": "Connection refused",
  "source_file": "app.py",
  "source_line": 42,
  "trace_id": "trace_example",
  "parent_event_id": null
}
```

Supported `event_type` values in the backend request model are `retrieval`, `context`, `generation`, `validation`, `error`, and `custom`. Supported statuses are `running`, `success`, `failed`, and `warning`.

`duration_ms` must be non-negative when supplied. The event payload is a flexible object; `error`, source location, trace ID, and parent event ID are optional. The backend rejects undeclared top-level event fields (`extra="forbid"`), while allowing flexible keys inside `payload`.

### Compare request schema

```json
{
  "baseline_run_id": "run_previous",
  "current_run_id": "run_current"
}
```

Both runs must exist and belong to the same project. The backend loads their events and generates findings with evidence event IDs.

### Finding schema (stored comparison result)

```json
{
  "finding_id": "fnd_example",
  "run_id": "run_current",
  "baseline_run_id": "run_previous",
  "rule_id": "empty_retrieval",
  "severity": "high",
  "title": "No chunks retrieved",
  "explanation": "The current retrieval event reports zero retrieved chunks.",
  "evidence_event_ids": ["evt_baseline", "evt_current"],
  "recommended_action": "Inspect the query, corpus, filters, index state, and retrieval thresholds.",
  "created_at": "2026-10-25T10:31:00Z"
}
```

The exact finding fields depend on the diagnostic rule. Evidence IDs should point to events in the compared runs.

### Investigation schema (stored report)

An investigation report contains a generated `investigation_id`, the `run_id`, the report fields, provider/AI status where applicable, and creation metadata. The structured report can include:

```json
{
  "title": "Generation endpoint is unreachable",
  "likely_cause": "The generation event reports a connection failure.",
  "confidence": "medium",
  "evidence_event_ids": ["evt_current"],
  "timeline": [
    {
      "event_id": "evt_current",
      "explanation": "The generation request failed with a connection error."
    }
  ],
  "historical_comparison": "A comparable successful run used a different endpoint.",
  "alternative_explanations": ["The service may be temporarily unavailable."],
  "recommended_actions": ["Verify the configured endpoint and service availability."],
  "limitations": ["The trace alone does not establish why the endpoint became unreachable."]
}
```

This is an example of the report contract, not a claim that these values exist in the uploaded database. The backend uses deterministic diagnosis and may optionally enrich it with Ollama.

### Incident-memory schema

```json
{
  "memory_id": "mem_example",
  "project_id": "prj_example",
  "run_id": "run_current",
  "investigation_id": "inv_example",
  "signature": "shortened_hash",
  "category": "connection",
  "stage": "generation",
  "evidence_event_ids": ["evt_current"],
  "outcome": "unverified",
  "verified_fix": null,
  "created_at": "2026-10-25T10:32:00Z",
  "source": "automatic_investigation"
}
```

The signature is derived from normalized error information. A memory starts as `unverified`; after explicit user confirmation, the backend records `outcome: "user_verified"`, `verified_fix`, `verified_at`, and `verification_source`.

### Schema relationship at a glance

```text
Project (project_id)
   |
   +-- Runs (run_id, project_id)
          |
          +-- Events (event_id, run_id)
          +-- Findings (finding_id, run_id, baseline_run_id)
          +-- Investigations (investigation_id, run_id)
          +-- Incident memories (memory_id, project_id, run_id, investigation_id)
```

MongoDB stores these as documents in separate collections. The IDs connect the records; these links are application-level relationships, not SQL foreign keys.


## 9. How Previous Successful Runs Are Stored and Retrieved

Historical comparison is central to TraceLens. It answers:

> What is different about this execution compared with a previous
> execution that worked?

### Investigation retrieval logic

When an investigation is requested, the backend in `app/main.py`:

1.  Loads the selected run by `run_id`.
2.  Loads that run's events in timestamp order.
3.  Retrieves up to **60 recent runs from the same project**, ordered
    newest first.
4.  Prioritizes successful runs, preferring matching scenario and
    version when available.
5.  Adds other successful runs when needed, then other project runs for
    additional context.
6.  Deduplicates by run ID and keeps a bounded set of up to **12 runs**
    for detailed investigation.
7.  Retrieves up to **40 events per selected historical run**, in
    timestamp order.
8.  Passes the current trace and selected history to comparison and
    diagnostic logic.

Runs with statuses such as `success`, `succeeded`, or `completed` are
treated as successful. The initial history query is limited to 60 runs;
the detailed historical event sample is bounded separately. These limits
keep investigations from loading unbounded history.

### What is compared?

The historical comparison logic in `app/investigation.py` normalizes
stages and compares the information actually recorded, including:

-   Stage presence and order where available
-   Stage status
-   Endpoints and model/configuration metadata
-   Relevant differences associated with a failed stage
-   Evidence event IDs and missing fields that prevent a reliable
    comparison

The logic prefers comparable successful runs from the same project,
especially those with matching scenario and version when possible. It
does not invent values for fields that were not captured.

### Example

``` text
Previous successful run:
  Generation endpoint = http://127.0.0.1:11434
  Generation status   = success

Current failed run:
  Generation endpoint = http://127.0.0.1:11435
  Generation status   = error
  Error               = connection refused
```

If those values were captured, the endpoint difference is evidence worth
investigating. It is not absolute proof that the endpoint change caused
the failure.

**If no suitable successful baseline exists**, TraceLens should report
that limitation. It can still diagnose a recorded error in the current
run, but it cannot claim a historical configuration change without
historical evidence.

## 9. Deterministic Diagnostics and Optional Ollama

TraceLens does not rely entirely on an LLM to diagnose failures.

### Deterministic stage

The backend examines recorded statuses and error messages to recognize
issues such as connection failures, timeouts, authentication errors,
upstream errors, model configuration problems, context-length errors,
retrieval failures, and malformed model output.

The report can contain a likely cause, confidence label, timeline,
evidence event IDs, alternative explanations, recommended actions, and
limitations.

### Optional LLM enrichment

When the backend is configured to use Ollama, it sends a bounded
representation of the current trace, relevant history, and the initial
diagnosis for enrichment. The model is instructed to distinguish facts
from hypotheses and to avoid inventing evidence. The backend validates
evidence references and preserves the trace-derived timeline.

If Ollama is unavailable, times out, or returns an unusable response,
the backend can fall back to the deterministic result.

**Design principle:** the LLM can explain and enrich the diagnosis, but
recorded evidence remains the basis of the investigation.

## 10. Incident Memory: Recurring Problems and Fixes

Historical run comparison asks what changed. **Incident memory** helps
track whether a similar failure has occurred before and whether a fix
was explicitly confirmed.

When a run is failed or contains a failed/error event, the backend can
create a project-scoped memory containing a redacted summary, category,
stage, signature, and references to the run and investigation.

### Signature and matching logic

The code in `app/memory.py` normalizes error text, redacts common
secrets, replaces URLs, normalizes longer numeric sequences and
whitespace, and hashes the category, stage, and normalized error text
with SHA-256.

The matching helper scores:

-   Exact signature match: **+5**
-   Same known error category: **+2**
-   Same known stage: **+2**

This is deterministic signature matching, not semantic vector search.

### How a fix is confirmed

A memory starts as **unverified**. A developer can submit a fix
description through `POST /api/memories/{memory_id}/confirm-fix`. The
backend records the sanitized fix, confirmation time, and
`user_verified` outcome.

This records explicit user confirmation; it does not mean TraceLens
independently ran the fix or proved that it resolved the incident.

## 11. Run Comparison and Findings

The explicit comparison endpoint is:

``` text
POST /api/runs/compare
```

The backend loads the baseline and current runs, checks that they belong
to the same project, loads their events, and invokes comparison logic in
`app/diagnostics.py`. Findings include details and evidence references
and are persisted in MongoDB.

This is distinct from the broader investigation flow, which gathers
project history and can use optional Ollama enrichment.

## 12. Frontend and Developer Experience

The React + TypeScript dashboard calls the backend API to:

1.  View backend health.
2.  Select or create a project.
3.  Browse runs.
4.  Inspect a run's event timeline.
5.  Review comparison findings.
6.  Request an investigation.
7.  Read the diagnosis, evidence, recommendations, and limitations.
8.  Review incident memories and record a confirmed fix.

The frontend does not access MongoDB directly. Keeping the API boundary
centralizes validation, persistence, and access-control logic.

## 13. Local Development with Docker

From the repository root, start MongoDB:

``` powershell
docker compose up -d mongodb
docker compose ps
```

The current local backend configuration uses:

``` dotenv
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=tracelens
```

Start the backend from `tracelens-backend`:

``` powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend from `tracelens-frontend`:

``` powershell
npm install
npm run dev
```

Typical local addresses:

-   Frontend: `http://127.0.0.1:5173`
-   Backend: `http://127.0.0.1:8000`
-   MongoDB: `mongodb://localhost:27017`

Run the customer-support RAG demo separately with its dependencies,
vector store, and Ollama model configured. If the backend itself runs in
a container, remember that `127.0.0.1` refers to that container; it does
not automatically refer to the host or another container.

## 14. Privacy and Security Considerations

The SDK includes payload sanitization, and the LangChain callback limits
automatic capture of raw text by recording summaries such as length and
hashes for string inputs/outputs. Incident-memory creation redacts
common credentials from error text.

These measures reduce exposure but are not a guarantee that every secret
or personal detail will always be removed. Review custom payloads,
metadata, error messages, retention, authentication, and project-level
authorization before production deployment. Local demo settings should
not be treated as production security settings.

## 15. Current Boundaries

-   Instrumentation covers supported integrations; arbitrary code may
    need explicit instrumentation.
-   Diagnosis quality depends on what the trace actually captured.
-   A historical difference supports a hypothesis but does not prove
    causation.
-   Missing historical data is an evidence gap, not proof of a change.
-   Ollama enrichment is optional; deterministic diagnosis provides the
    baseline.
-   Incident-memory fix confirmation is user-reported, not independent
    verification.
-   TraceLens diagnoses and recommends actions; it does not
    automatically modify the developer's code or guarantee a fix.

## 16. Summary

TraceLens creates a repeatable observability workflow:

**Instrument → Capture runs and events → Store history → Compare against
successful runs → Diagnose with evidence → Optionally enrich with an LLM
→ Save incident memory → Review in the dashboard.**

Its central benefit is giving developers a structured explanation of
what happened, what changed compared with previous executions, which
evidence supports a diagnosis, and what to investigate next.
