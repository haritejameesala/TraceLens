"""Optional live MongoDB API contract tests.

Set TRACELENS_TEST_MONGODB_URI to run these tests against a disposable MongoDB
instance. The suite creates a dedicated database and drops it at teardown.
"""
import os
import uuid
import pytest

TEST_URI = os.getenv("TRACELENS_TEST_MONGODB_URI")
pytestmark = pytest.mark.skipif(not TEST_URI, reason="set TRACELENS_TEST_MONGODB_URI to run live MongoDB integration tests")

if TEST_URI:
    os.environ["MONGODB_URI"] = TEST_URI
    os.environ["MONGODB_DATABASE"] = f"tracelens_test_{uuid.uuid4().hex[:10]}"

    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import client as mongo_client, db


def test_project_run_event_lifecycle_and_duplicate_event_idempotency():
    with TestClient(app) as api:
        key = f"test-project-{uuid.uuid4().hex[:10]}"
        created = api.post("/api/projects", json={"project_key": key, "name": "Integration Project", "framework": "python"})
        assert created.status_code == 201
        project = created.json()
        project_id = project["project_id"]

        duplicate = api.post("/api/projects", json={"project_key": key, "name": "Integration Project", "framework": "python"})
        assert duplicate.status_code == 200
        assert duplicate.json()["project_id"] == project_id

        run_response = api.post("/api/runs", json={"project_id": project_id, "scenario": "failure-matrix", "status": "running"})
        assert run_response.status_code == 201
        run_id = run_response.json()["run_id"]

        event = {"event_id": f"evt_{uuid.uuid4().hex}", "step": "generation", "event_type": "error",
                 "status": "failed", "error": "model not found", "payload": {"exception_type": "ModelNotFound"}}
        first = api.post(f"/api/runs/{run_id}/events", json=event)
        second = api.post(f"/api/runs/{run_id}/events", json=event)
        assert first.status_code == 201 and first.json()["status"] == "stored"
        assert second.status_code == 201 and second.json()["status"] == "duplicate_ignored"
        events = api.get(f"/api/runs/{run_id}/events")
        assert events.status_code == 200 and len(events.json()) == 1

        delete = api.delete(f"/api/projects/{project_id}")
        assert delete.status_code == 200
        assert api.get(f"/api/runs/{run_id}").status_code == 404


def test_cross_project_baseline_comparison_is_rejected():
    with TestClient(app) as api:
        project_ids = []
        run_ids = []
        for name in ("Project A", "Project B"):
            response = api.post("/api/projects", json={"project_key": f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}", "name": name, "framework": "python"})
            assert response.status_code == 201
            project_ids.append(response.json()["project_id"])
            run = api.post("/api/runs", json={"project_id": response.json()["project_id"], "scenario": "test"})
            assert run.status_code == 201
            run_ids.append(run.json()["run_id"])
        comparison = api.post("/api/runs/compare", json={"baseline_run_id": run_ids[0], "current_run_id": run_ids[1]})
        assert comparison.status_code == 400
        for project_id in project_ids:
            api.delete(f"/api/projects/{project_id}")


def teardown_module():
    if TEST_URI:
        mongo_client.drop_database(db.name)
        mongo_client.close()
