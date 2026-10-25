import hashlib
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.config import settings
from app import main
from app.main import app


def test_projects_preflight_reaches_cors_without_session_assertion(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    client = TestClient(app)

    response = client.options(
        "/api/projects",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_api_without_session_returns_unauthorized_instead_of_server_error(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    client = TestClient(app)

    response = client.get("/api/projects")

    assert response.status_code == 401
    assert response.json()["detail"] == "Sign in required"


def test_project_sdk_key_can_ingest_only_its_project_runs(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    key = "tlproj-test-secret"
    project_id = "project-owned"
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    inserted_runs = []
    inserted_events = []

    class Projects:
        async def find_one(self, query, projection=None):
            if query.get("project_id") == project_id and (
                "api_key_hash" not in query or query["api_key_hash"] == key_hash
            ):
                return {"project_id": project_id}
            return None

    class Runs:
        documents = {}

        async def find_one(self, query, projection=None):
            return self.documents.get(query.get("run_id"))

        async def insert_one(self, document):
            inserted_runs.append(document)
            self.documents[document["run_id"]] = document

        async def update_one(self, query, update):
            return SimpleNamespace(matched_count=int(query.get("run_id") in self.documents))

    class Events:
        async def insert_one(self, document):
            inserted_events.append(document)

    monkeypatch.setattr(main, "db", SimpleNamespace(projects=Projects(), runs=Runs(), events=Events()))
    client = TestClient(app)

    created = client.post(
        "/api/runs",
        headers={"Authorization": f"Bearer {key}"},
        json={"project_id": project_id, "scenario": "sdk-auth"},
    )
    assert created.status_code == 201
    assert len(inserted_runs) == 1
    run_id = created.json()["run_id"]

    event_response = client.post(
        f"/api/runs/{run_id}/events",
        headers={"Authorization": f"Bearer {key}"},
        json={"event_id": "event-1", "step": "generation", "event_type": "custom"},
    )
    assert event_response.status_code == 201
    assert len(inserted_events) == 1

    status_response = client.patch(
        f"/api/runs/{run_id}",
        headers={"Authorization": f"Bearer {key}"},
        json={"status": "success"},
    )
    assert status_response.status_code == 200

    wrong_project = client.post(
        "/api/runs",
        headers={"Authorization": f"Bearer {key}"},
        json={"project_id": "another-project", "scenario": "sdk-auth"},
    )
    assert wrong_project.status_code == 401
    read_response = client.get(
        "/api/projects",
        headers={"Authorization": f"Bearer {key}"},
    )
    assert read_response.status_code == 403


def test_project_sdk_key_cannot_write_without_valid_project_binding(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    client = TestClient(app)

    response = client.post(
        "/api/runs",
        headers={"Authorization": "Bearer invalid-key"},
        json={"project_id": "unknown-project", "scenario": "sdk-auth"},
    )

    assert response.status_code == 401
