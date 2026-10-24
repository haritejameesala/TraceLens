"""Deterministic TF-IDF RAG demo with opt-in TraceLens instrumentation."""
import os
import httpx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from tracelens_sdk import TraceLens

API = os.getenv("TRACELENS_API_URL", "http://127.0.0.1:8000")
QUESTION = "What is the minimum password length?"
DOCS = [
    {"id": "security-01", "text": "The minimum password length is fourteen characters. Company passwords must be at least 14 characters long."},
    {"id": "security-02", "text": "Remote access requires multi-factor authentication."},
    {"id": "security-03", "text": "Employees must never share passwords with colleagues."},
]


def retrieve(question, broken=False):
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    matrix = vectorizer.fit_transform([d["text"] for d in DOCS] + [question])
    scores = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
    ranked = sorted(zip(scores, DOCS), key=lambda item: item[0], reverse=True)
    results = [dict(doc, score=float(score)) for score, doc in ranked if score > 0.01][:2]
    # Deliberate demo fault: simulates a bad post-retrieval filter.
    return [] if broken else results


def answer(docs):
    return docs[0]["text"] if docs else "No relevant evidence was retrieved."


def main():
    with httpx.Client(base_url=API, timeout=10) as client:
        client.get("/health").raise_for_status()
        response = client.post("/api/projects", json={"name": "RAG Project 1 - TF-IDF", "description": "Standalone TF-IDF RAG", "framework": "custom-python-tfidf"})
        response.raise_for_status()
        project_id = response.json()["project_id"]

    def execute(tracer, name, version, broken, baseline=None):
        with tracer.start_run(name, version=version, baseline_run_id=baseline,
                              metadata={"project": "rag-project-1", "retriever": "tfidf"}) as run:
            payload = {"query": QUESTION, "retriever": "tfidf", "version": version}
            with run.trace_step("retrieve_documents", event_type="retrieval", payload=payload):
                docs = retrieve(QUESTION, broken)
                payload.update({"relevant_chunk_count": sum(d["id"] == "security-01" for d in docs),
                                "retrieved_chunk_count": len(docs), "chunk_ids": [d["id"] for d in docs],
                                "scores": [round(d["score"], 4) for d in docs]})
            generation = {}
            with run.trace_step("generate_answer", event_type="generation", payload=generation):
                result = answer(docs)
                generation.update({"answer_supported": bool(docs), "output_summary": result[:160]})
            print(f"{name}: {result}")
            return run.run_id, docs

    with TraceLens(project_id, api_url=API, strict=True) as tracer:
        baseline, baseline_docs = execute(tracer, "baseline-success", "tfidf-v1", False)
        if not baseline_docs or baseline_docs[0]["id"] != "security-01":
            raise RuntimeError("Baseline evaluation failed: expected security-01 as the top result")
        current, current_docs = execute(tracer, "retrieval-regression", "tfidf-v2-buggy-filter", True, baseline)
        if current_docs:
            raise RuntimeError("Regression evaluation failed: expected the deliberately broken filter to return no results")

    with httpx.Client(base_url=API, timeout=10) as client:
        response = client.post("/api/runs/compare", json={"baseline_run_id": baseline, "current_run_id": current})
        response.raise_for_status()
        comparison = response.json()
        print("TraceLens comparison:", comparison)
    print("Project:", project_id, "Baseline:", baseline, "Current:", current)

if __name__ == "__main__":
    main()
