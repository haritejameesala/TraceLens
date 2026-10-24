"""Minimal custom-Python integration example. Requires a running TraceLens backend."""
import os
from tracelens_sdk import TraceLens, traced_step

project_id = os.environ["TRACELENS_PROJECT_ID"]
api_url = os.getenv("TRACELENS_API_URL", "http://127.0.0.1:8000")


def retrieve(question: str):
    # Replace this stub with your real retriever. Never pass raw customer content
    # into telemetry unless your privacy policy explicitly permits it.
    return [{"chunk_id": "policy-001", "score": 0.91}]

with TraceLens(project_id=project_id, api_url=api_url, strict=False) as tracer:
    with tracer.start_run("custom-rag", version="1.0.0", metadata={"environment": "local"}) as run:
        @traced_step(run, "retrieve", event_type="retrieval")
        def instrumented_retrieve(question: str):
            return retrieve(question)

        docs = instrumented_retrieve("example question")
        run.record_custom_event(
            step="retrieval.summary", event_type="retrieval", status="success",
            payload={"retrieved_chunk_count": len(docs), "chunk_ids": [d["chunk_id"] for d in docs]},
        )
        with run.trace_step("generate", event_type="generation", payload={"model": "example-model"}):
            answer = "Example answer grounded in retrieved evidence."
        print(answer)
