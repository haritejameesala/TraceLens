import pytest
from pydantic import ValidationError
from app.models import EventCreate, ProjectCreate, RunCreate, RunUpdate


def test_event_rejects_negative_duration_and_invalid_status():
    base = {"event_id": "evt-1", "step": "generation", "event_type": "generation"}
    with pytest.raises(ValidationError):
        EventCreate(**base, duration_ms=-1)
    with pytest.raises(ValidationError):
        EventCreate(**base, status="mystery")


def test_event_rejects_unexpected_fields_to_keep_schema_explicit():
    with pytest.raises(ValidationError):
        EventCreate(event_id="evt-1", step="generation", event_type="generation", secret="do-not-store")


def test_event_allows_missing_duration_and_defaults_timestamp():
    event = EventCreate(event_id="evt-1", step="retrieval", event_type="retrieval")
    assert event.duration_ms is None
    assert event.timestamp is not None
    assert event.payload == {}


def test_project_key_is_constrained_and_name_cannot_be_blank():
    with pytest.raises(ValidationError):
        ProjectCreate(name="", project_key="valid-key")
    with pytest.raises(ValidationError):
        ProjectCreate(name="Support", project_key="Invalid Spaces")


def test_run_status_accepts_only_supported_lifecycle_values():
    assert RunUpdate(status="failed").status == "failed"
    with pytest.raises(ValidationError):
        RunUpdate(status="cancelled")


def test_run_metadata_defaults_to_independent_empty_dicts():
    first = RunCreate(project_id="p", scenario="s1")
    second = RunCreate(project_id="p", scenario="s2")
    first.metadata["x"] = 1
    assert second.metadata == {}
