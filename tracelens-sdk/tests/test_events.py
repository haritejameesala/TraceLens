from tracelens_sdk import TraceEvent


def test_event_serializes_timestamp_and_optional_fields():
    event = TraceEvent(step="retrieve", event_type="retrieval", payload={"relevant_chunk_count": 2}, duration_ms=12.5)
    data = event.to_dict()
    assert data["step"] == "retrieve"
    assert data["event_type"] == "retrieval"
    assert data["duration_ms"] == 12.5
    assert data["timestamp"].endswith("+00:00")


def test_event_omits_optional_fields_when_unset():
    data = TraceEvent(step="custom").to_dict()
    assert "error" not in data
    assert "duration_ms" not in data
