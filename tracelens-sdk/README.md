# TraceLens SDK

Install from this directory with `pip install -e .`. Use `TraceLens(project_id, api_url=..., strict=True)` after creating a project through the backend. `strict=True` surfaces delivery failures; use `strict=False` only when application continuity is preferred, and inspect delivery outcomes/logging in your application. The SDK sends HTTP events to FastAPI; it does not connect directly to MongoDB.

Only include safe, explicit metadata in event payloads. Do not include credentials, tokens, or full sensitive request bodies.

## Automatic LangChain instrumentation (optional)

Install the optional integration:

```bash
pip install 'tracelens-sdk[langchain]'
```

Configure `TRACELENS_PROJECT_ID` and optionally `TRACELENS_API_URL`, then attach the callback to a supported LangChain invocation:

```python
import os
from tracelens_sdk import TraceLens, langchain_callback

tracer = TraceLens(
    project_id=os.environ["TRACELENS_PROJECT_ID"],
    api_url=os.getenv("TRACELENS_API_URL", "http://127.0.0.1:8000"),
    strict=False,
)
callback = langchain_callback(tracer, run_name="support-rag", version="1.0")
# Example: chain.invoke({"input": question}, config={"callbacks": [callback]})
```

This captures supported LangChain chain, retriever, and model callback boundaries. It does not instrument arbitrary Python functions or automatically infer relevance labels. `relevant_chunk_count` is deliberately not guessed by this integration; domain-specific relevance evaluation requires an evaluator or explicit metadata. Attach the callback to each invocation (or configure it in your framework's supported callback configuration). Use manual TraceLens events for custom pipeline steps. Close `tracer` during application shutdown.

For production use, avoid putting raw prompts, completions, personal data, or secrets into event payloads. The integration records counts and metadata rather than raw document contents by default.

## SDK tests

From this directory, install the package and test dependencies, then run `python -m pytest tests`. The tests use an in-memory HTTP transport and do not require MongoDB.
