from app.investigation import deterministic_diagnosis, safe_value


def test_model_not_found_is_diagnosed_with_evidence():
    run = {"run_id": "run_1", "status": "failed"}
    events = [{"event_id": "evt_1", "step": "generation", "event_type": "generation", "status": "failed", "error": "model 'qwen2.5:3b' not found (status code: 404)", "timestamp": "2026-10-24T10:00:00Z"}]
    result = deterministic_diagnosis(run, events, [run, {"run_id": "run_0", "status": "success"}])
    assert "Model unavailable" in result["title"]
    assert result["evidence_event_ids"] == ["evt_1"]
    assert result["history_context"]["successful_runs"] == 1


def test_failed_run_without_error_event_reports_instrumentation_gap():
    result = deterministic_diagnosis({"run_id": "run_2", "status": "failed"}, [], [])
    assert "without a recorded error" in result["title"]
    assert result["confidence"] == "low"


def test_sensitive_payload_fields_redacted():
    result = safe_value({"api_key": "secret-value", "normal": "safe"})
    assert result["api_key"] == "[REDACTED]"
    assert result["normal"] == "safe"
