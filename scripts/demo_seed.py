"""Seed a realistic TraceLens demo without touching existing projects.

Run from the repository root after starting the API:
    python scripts/demo_seed.py
Optional environment:
    TRACELENS_API_URL=http://127.0.0.1:8000
    TRACELENS_API_KEY=your-development-key
"""
import os
import httpx

BASE_URL = os.getenv("TRACELENS_API_URL", "http://127.0.0.1:8000").rstrip("/")
HEADERS = {"X-API-Key": os.environ["TRACELENS_API_KEY"]} if os.getenv("TRACELENS_API_KEY") else {}
POLICY = """RAG retrieval incident runbook.
If the retriever returns zero relevant chunks, inspect the active collection, query normalization, metadata filters, embedding model version, and minimum similarity threshold.
A successful baseline for the employee password policy question should retrieve the security password policy chunk. Do not treat an empty context as a supported answer.
When comparing releases, compare retrieved chunk IDs and scores before assuming the language model caused the regression.
"""


def main():
    with httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=15) as api:
        api.get("/health").raise_for_status()
        project = api.post("/api/projects", json={
            "name": "TraceLens Demo — RAG regression",
            "description": "Reproducible baseline/current traces with a deliberate empty-retrieval regression.",
            "framework": "python-demo",
        })
        project.raise_for_status()
        project_id = project.json()["project_id"]

        doc = api.post(f"/api/projects/{project_id}/knowledge", json={
            "title": "Retrieval regression runbook", "source": "demo://runbook", "content": POLICY,
        })
        doc.raise_for_status()

        def create_run(scenario, version):
            response = api.post("/api/runs", json={
                "project_id": project_id, "scenario": scenario, "version": version,
                "status": "running", "metadata": {"demo": True},
            })
            response.raise_for_status()
            return response.json()["run_id"]

        def event(run_id, event_id, step, event_type, payload, status="success", error=None, duration=12.0):
            response = api.post(f"/api/runs/{run_id}/events", json={
                "event_id": event_id, "step": step, "event_type": event_type, "status": status,
                "payload": payload, "error": error, "duration_ms": duration,
            })
            response.raise_for_status()

        baseline = create_run("Password policy — baseline", "v1.4.0")
        event(baseline, "demo_baseline_retrieval", "retrieve_documents", "retrieval",
              {"query": "minimum password length", "relevant_chunk_count": 3,
               "chunk_ids": ["security-01", "security-02", "security-03"], "retriever": "tfidf"})
        event(baseline, "demo_baseline_generation", "generate_answer", "generation",
              {"answer_supported": True, "output_summary": "Passwords must be at least 14 characters."}, duration=420)
        api.patch(f"/api/runs/{baseline}", json={"status": "success"}).raise_for_status()

        current = create_run("Password policy — regression", "v1.5.0")
        event(current, "demo_current_retrieval", "retrieve_documents", "retrieval",
              {"query": "minimum password length", "relevant_chunk_count": 0,
               "chunk_ids": [], "retriever": "tfidf", "filter": "security-policy-v2"})
        event(current, "demo_current_generation", "generate_answer", "generation",
              {"answer_supported": False, "output_summary": "No relevant evidence was retrieved."}, status="warning", duration=105)
        api.patch(f"/api/runs/{current}", json={"status": "failed"}).raise_for_status()

        comparison = api.post("/api/runs/compare", json={
            "baseline_run_id": baseline, "current_run_id": current,
        })
        comparison.raise_for_status()
        diagnosis = api.post(f"/api/projects/{project_id}/diagnose", json={
            "question": "Why did the password-policy answer regress between the two versions?",
            "run_id": current, "top_k": 5,
        })
        diagnosis.raise_for_status()

        print("TraceLens demo created.")
        print(f"Project: {project_id}")
        print(f"Baseline run: {baseline}")
        print(f"Current run: {current}")
        print(f"Findings: {len(comparison.json().get('findings', []))}")
        print(f"Diagnosis mode: {diagnosis.json().get('mode')}")
        print(f"Open dashboard: {BASE_URL}/")


if __name__ == "__main__":
    main()
