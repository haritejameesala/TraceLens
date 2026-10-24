"""Semantic RAG demo using ChromaDB + SentenceTransformers with TraceLens tracing."""
import os
import httpx
import chromadb
from sentence_transformers import SentenceTransformer
from tracelens_sdk import TraceLens

API = os.getenv("TRACELENS_API_URL", "http://127.0.0.1:8000")
MODEL_NAME = os.getenv("TRACELENS_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
QUESTION = "How long must an employee password be?"
DOCS = [
    {"id": "policy-a", "text": "The minimum length for employee passwords is fourteen characters."},
    {"id": "policy-b", "text": "All remote sessions must use multi-factor authentication."},
    {"id": "policy-c", "text": "Never disclose account credentials to another person."},
]


class ChromaRAG:
    def __init__(self):
        # Ephemeral Chroma keeps the example self-contained and avoids stale local indexes.
        self.client = chromadb.Client()
        self.collection = self.client.get_or_create_collection("tracelens_policy_demo")
        self.embedder = SentenceTransformer(MODEL_NAME)
        vectors = self.embedder.encode([doc["text"] for doc in DOCS]).tolist()
        self.collection.upsert(ids=[doc["id"] for doc in DOCS], documents=[doc["text"] for doc in DOCS], embeddings=vectors)

    def retrieve(self, question, broken=False):
        vector = self.embedder.encode([question]).tolist()
        result = self.collection.query(query_embeddings=vector, n_results=len(DOCS))
        found = [
            {"id": chunk_id, "text": text, "distance": float(distance)}
            for chunk_id, text, distance in zip(result["ids"][0], result["documents"][0], result["distances"][0])
        ]
        # This deliberate fault models a bad downstream filter; normal retrieval is unchanged.
        return [] if broken else found[:2]


def answer(docs):
    return docs[0]["text"] if docs else "No relevant evidence was retrieved."


def main():
    rag = ChromaRAG()
    with httpx.Client(base_url=API, timeout=10) as client:
        client.get("/health").raise_for_status()
        response = client.post("/api/projects", json={
            "name": "RAG Project 2 - ChromaDB",
            "description": "Standalone semantic RAG",
            "framework": "chromadb-sentence-transformers",
        })
        response.raise_for_status()
        project_id = response.json()["project_id"]

    def execute(tracer, name, version, broken, baseline=None):
        with tracer.start_run(name, version=version, baseline_run_id=baseline,
                              metadata={"project": "rag-project-2", "vector_store": "chroma", "embedding_model": MODEL_NAME}) as run:
            payload = {"query": QUESTION, "vector_store": "chroma", "version": version}
            with run.trace_step("retrieve_documents", event_type="retrieval", payload=payload):
                docs = rag.retrieve(QUESTION, broken)
                payload.update({
                    "relevant_chunk_count": sum(doc["id"] == "policy-a" for doc in docs),
                    "retrieved_chunk_count": len(docs),
                    "chunk_ids": [doc["id"] for doc in docs],
                    "distances": [round(doc["distance"], 4) for doc in docs],
                })
            generation_payload = {}
            with run.trace_step("generate_answer", event_type="generation", payload=generation_payload):
                result = answer(docs)
                generation_payload.update({"answer_supported": bool(docs), "output_summary": result[:160]})
            print(f"{name}: {result}")
            return run.run_id, docs

    with TraceLens(project_id, api_url=API, strict=True) as tracer:
        baseline, baseline_docs = execute(tracer, "baseline-success", "chroma-v1", False)
        if not baseline_docs or baseline_docs[0]["id"] != "policy-a":
            raise RuntimeError("Baseline evaluation failed: expected policy-a as the top semantic result")
        current, current_docs = execute(tracer, "retrieval-regression", "chroma-v2-buggy-filter", True, baseline)
        if current_docs:
            raise RuntimeError("Regression evaluation failed: expected the deliberate faulty filter to return no results")

    with httpx.Client(base_url=API, timeout=10) as client:
        response = client.post("/api/runs/compare", json={"baseline_run_id": baseline, "current_run_id": current})
        response.raise_for_status()
        comparison = response.json()
        print("TraceLens comparison:", comparison)
    print("Project:", project_id, "Baseline:", baseline, "Current:", current)


if __name__ == "__main__":
    main()
