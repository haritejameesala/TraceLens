# Customer Support Knowledge Assistant (real-world LangChain integration)

This is a small but realistic internal support knowledge assistant built around operational topics: account security, billing, incident communications, and privacy requests. It uses a local Chroma vector store, Sentence Transformers embeddings, LangChain LCEL, and Ollama for local generation. It does not use injected failure behavior or hard-coded answers.

The project is also TraceLens's automatic-instrumentation reference integration: there are **no manual `trace_step()` calls**. Each user request invokes the LangChain chain with one `TraceLensCallbackHandler`; LangChain propagates callback events to supported chain, retriever, and model operations. TraceLens stores metadata and counts, not raw questions, prompts, answers, or document contents.

## Prerequisites

- Python 3.10 or 3.11 recommended
- TraceLens backend and MongoDB running
- Node.js only if you want the dashboard (the frontend is in `../tracelens-frontend`)
- [Ollama](https://ollama.com/) running locally

## Install on Windows PowerShell

From the TraceLens project root, assuming this folder is `rag-customer-support`:

```powershell
cd .\tracelens-sdk
python -m pip install -e ".[langchain]"
cd ..\rag-customer-support
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

The app can register its project automatically on first launch using the stable key `customer-support-rag`. Leave `TRACELENS_PROJECT_ID` blank to use this behavior. If you provide an existing project ID, the app reuses it. Project registration is idempotent, so repeated launches do not create new project cards.

Pull and start a local model:

```powershell
ollama pull qwen2.5:3b
ollama serve
```

If Ollama is already running as a service, you do not need to run `ollama serve` again. Then start the assistant:

```powershell
python main.py
```

The first run downloads the embedding model and builds the local Chroma index from the Markdown articles. Subsequent starts reconcile stable content-derived chunk IDs, add new chunks, and remove stale chunks so edits to articles are reflected without blindly re-embedding the entire knowledge base. This example is intended for a local development environment; review persistence, access controls, and model governance before using customer data in production.

## Verify automatic instrumentation

1. Ask: `How do I handle a failed payment?`
2. Ask: `What should support do if a customer requests data deletion?`
3. Ask an unanswerable question, such as: `What exact percentage discount do I get next year?`
4. In TraceLens, open the project and inspect the newest `customer-support-rag` runs.
5. Inspect events. Expected event types include chain/custom events, retrieval events with retrieved chunk counts, and generation events. Events should not contain raw question or answer text.
6. Compare runs to review the event timeline and diagnostics. Retrieval count is observed, not equivalent to semantic relevance; relevance evaluation requires a labeled evaluator.

## What this proves—and what it doesn't

- Proves automatic callback-based observation for supported LangChain operations without manual step wrappers.
- Does not claim automatic tracing of arbitrary Python functions or frameworks without integrations.
- Does not automatically infer semantic relevance from document count.
- Uses a local Ollama model to avoid requiring a hosted LLM API key. Model quality and speed depend on your machine and installed model.
- The bundled knowledge articles are example organizational content, not legal or security policy advice; replace them with approved, access-controlled documents before real organizational use.

## Privacy notes

The callback intentionally records operation names, counts, timing, exception type/message (bounded), and framework run IDs. Avoid adding raw prompts, answers, or document content to metadata. For multi-user deployment, add authentication, authorization, tenant isolation, retention controls, and secret management before exposing the backend beyond localhost.
