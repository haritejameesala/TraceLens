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


def test_diagnosis_timeline_preserves_recorded_events_in_order():
    events = [
        {"event_id": "evt_start", "step": "run.started", "status": "success", "timestamp": "2026-10-24T10:00:00Z"},
        {"event_id": "evt_retrieval", "step": "retrieval", "status": "success", "timestamp": "2026-10-24T10:00:01Z"},
        {"event_id": "evt_model", "step": "generation", "status": "failed", "error": "[WinError 10061] connection refused", "timestamp": "2026-10-24T10:00:02Z"},
        {"event_id": "evt_finish", "step": "run.failed", "status": "failed", "timestamp": "2026-10-24T10:00:02Z"},
    ]
    result = deterministic_diagnosis({"run_id": "run_x", "status": "failed"}, events, [])
    assert [item["event_id"] for item in result["timeline"]] == ["evt_start", "evt_retrieval", "evt_model", "evt_finish"]
    assert result["evidence_event_ids"] == ["evt_model", "evt_finish"] or "evt_model" in result["evidence_event_ids"]
    assert "connection failure" in result["likely_cause"].lower()


def test_connection_refused_identifies_endpoint_and_does_not_claim_service_is_down():
    run = {"run_id": "run_conn", "status": "failed"}
    events = [
        {"event_id": "evt_retrieval", "step": "retriever", "event_type": "retrieval", "status": "success", "timestamp": "2026-10-24T10:00:00Z", "payload": {"retrieved_chunk_count": 4}},
        {"event_id": "evt_generation", "step": "generation", "event_type": "error", "status": "failed", "timestamp": "2026-10-24T10:00:01Z", "error": "[WinError 10061] No connection could be made because the target machine actively refused it at 127.0.0.1:11435"},
    ]
    result = deterministic_diagnosis(run, events, [])
    assert "Connection refused" in result["title"]
    assert "127.0.0.1:11435" in result["likely_cause"]
    assert "may be stopped" in result["likely_cause"]
    assert "evt_generation" in result["evidence_event_ids"]
    assert "evt_retrieval" in result["evidence_event_ids"]
    assert [x["event_id"] for x in result["timeline"]] == ["evt_retrieval", "evt_generation"]


def test_safe_value_redacts_credentials_embedded_in_error_strings():
    result = safe_value({"error": "request failed with api_key=abc123secret"})
    assert "abc123secret" not in result["error"]


def test_diagnosis_includes_prior_event_as_context_not_as_cause():
    events = [
        {"event_id": "evt_a", "step": "retrieval", "status": "success", "timestamp": "2026-10-24T10:00:00Z"},
        {"event_id": "evt_b", "step": "generation", "status": "failed", "error": "WinError 10061 connection refused", "timestamp": "2026-10-24T10:00:01Z"},
    ]
    report = deterministic_diagnosis({"run_id": "run", "status": "failed"}, events, [])
    assert report["last_confirmed_event_id"] == "evt_a"
    assert report["first_failure_event_id"] == "evt_b"
    assert "does not prove" in report["limitations"][-1]


def test_event_schema_accepts_running_phase_and_trace_correlation():
    from app.models import EventCreate
    event = EventCreate(event_id="evt_running", step="retrieve.started", event_type="retrieval",
                        status="running", payload={"phase": "start"}, trace_id="run_123")
    assert event.status == "running"
    assert event.trace_id == "run_123"


def test_history_first_comparison_finds_recorded_endpoint_change():
    from app.investigation import compare_with_history
    current_run = {"run_id": "run_bad", "project_id": "p1", "scenario": "customer-support", "version": "1.0", "status": "failed"}
    current_events = [
        {"event_id": "evt_bad", "run_id": "run_bad", "step": "generation", "event_type": "error", "status": "failed",
         "timestamp": "2026-10-24T10:01:00Z", "error": "[WinError 10061] connection refused",
         "payload": {"ollama_base_url": "http://127.0.0.1:11435", "model": "qwen2.5:1.5b"}},
    ]
    history = [
        {"run_id": "run_good", "project_id": "p1", "scenario": "customer-support", "version": "1.0", "status": "success", "created_at": "2026-10-24T10:00:00Z"},
        current_run,
    ]
    historical_events = [
        {"event_id": "evt_good_gen", "run_id": "run_good", "step": "generation", "event_type": "generation", "status": "success",
         "timestamp": "2026-10-24T10:00:01Z", "payload": {"ollama_base_url": "http://127.0.0.1:11434", "model": "qwen2.5:1.5b"}},
    ]
    result = compare_with_history(current_run, current_events, history, historical_events)
    assert result["history_used"] is True
    assert result["endpoint_differences"]
    difference = result["endpoint_differences"][0]
    assert difference["historical_value"] == "http://127.0.0.1:11434"
    assert difference["current_value"] == "http://127.0.0.1:11435"
    assert "previous successful run" in result["summary"]


def test_deterministic_diagnosis_uses_history_not_just_run_counts():
    run = {"run_id": "run_bad", "project_id": "p1", "scenario": "customer-support", "version": "1.0", "status": "failed"}
    events = [{"event_id": "evt_bad", "run_id": "run_bad", "step": "generation", "event_type": "error", "status": "failed",
               "timestamp": "2026-10-24T10:01:00Z", "error": "[WinError 10061] connection refused",
               "payload": {"ollama_base_url": "http://127.0.0.1:11435"}}]
    history = [{"run_id": "run_good", "project_id": "p1", "scenario": "customer-support", "version": "1.0", "status": "success"}]
    historical_events = [{"event_id": "evt_good", "run_id": "run_good", "step": "generation", "status": "success",
                          "timestamp": "2026-10-24T10:00:01Z", "payload": {"ollama_base_url": "http://127.0.0.1:11434"}}]
    result = deterministic_diagnosis(run, events, history, historical_events)
    assert "endpoint difference" in result["likely_cause"].lower()
    assert "11434" in result["likely_cause"] and "11435" in result["likely_cause"]
    assert result["historical_differences"]["endpoint_differences"]


def test_history_comparison_does_not_compare_retrieval_operation_to_generation_operation():
    from app.investigation import compare_with_history
    current = {"run_id": "bad", "project_id": "p", "scenario": "same", "version": "1", "status": "failed"}
    history = [{"run_id": "good", "project_id": "p", "scenario": "same", "version": "1", "status": "success"}]
    current_events = [
        {"event_id": "cur_retrieval", "run_id": "bad", "step": "retriever", "event_type": "retrieval", "status": "success", "payload": {"phase": "end", "operation": "retrieval", "retrieved_chunk_count": 4}},
        {"event_id": "cur_generation", "run_id": "bad", "step": "generation", "event_type": "error", "status": "failed", "error": "connection refused", "payload": {"phase": "error", "operation": "generation", "model": "qwen2.5:1.5b"}},
    ]
    old_events = [
        {"event_id": "old_retrieval", "run_id": "good", "step": "retriever", "event_type": "retrieval", "status": "success", "payload": {"phase": "end", "operation": "retrieval", "retrieved_chunk_count": 4}},
        {"event_id": "old_generation", "run_id": "good", "step": "generation", "event_type": "generation", "status": "success", "payload": {"phase": "end", "operation": "generation", "model": "qwen2.5:1.5b"}},
    ]
    result = compare_with_history(current, current_events, history, old_events)
    assert not any(d["field"].endswith("operation") or d["field"].endswith("phase") for c in result["comparisons"] for d in c["field_differences"])
    assert not any("retrieval" in d["field"] and "generation" in d["field"] for d in result["endpoint_differences"])


def test_history_comparison_finds_endpoint_in_run_metadata():
    from app.investigation import compare_with_history
    current = {"run_id": "bad", "project_id": "p", "scenario": "same", "version": "1", "status": "failed", "metadata": {"llm_endpoint": "http://127.0.0.1:11435"}}
    history = [{"run_id": "good", "project_id": "p", "scenario": "same", "version": "1", "status": "success", "metadata": {"llm_endpoint": "http://127.0.0.1:11434"}}]
    result = compare_with_history(current, [], history, [])
    assert result["endpoint_differences"]
    diff = result["endpoint_differences"][0]
    assert diff["historical_value"] == "http://127.0.0.1:11434"
    assert diff["current_value"] == "http://127.0.0.1:11435"


def test_endpoint_difference_promoted_for_connection_refused_even_without_endpoint_in_exception():
    run = {"run_id": "bad", "project_id": "p", "scenario": "same", "version": "1", "status": "failed", "metadata": {"llm_endpoint": "http://127.0.0.1:11435"}}
    events = [{"event_id": "evt_fail", "run_id": "bad", "step": "generation", "event_type": "error", "status": "failed", "timestamp": "2026-10-24T10:00:00Z", "error": "[WinError 10061] connection refused"}]
    history = [{"run_id": "good", "project_id": "p", "scenario": "same", "version": "1", "status": "success", "metadata": {"llm_endpoint": "http://127.0.0.1:11434"}}]
    historical_events = [{"event_id": "evt_good_gen", "run_id": "good", "step": "generation", "event_type": "generation", "status": "success", "timestamp": "2026-10-24T09:00:00Z"}]
    result = deterministic_diagnosis(run, events, history, historical_events)
    assert "http://127.0.0.1:11434" in result["likely_cause"]
    assert "http://127.0.0.1:11435" in result["likely_cause"]
    assert "endpoint_differences" in result["historical_differences"]


def test_history_reports_current_endpoint_when_baseline_never_recorded_it():
    from app.investigation import compare_with_history
    current = {
        "run_id": "run_bad", "project_id": "p1", "scenario": "customer-support",
        "version": "1.0", "status": "failed",
        "metadata": {"llm_endpoint": "http://127.0.0.1:11435"},
    }
    history = [{
        "run_id": "run_good", "project_id": "p1", "scenario": "customer-support",
        "version": "1.0", "status": "success", "created_at": "2026-10-24T10:00:00Z",
        "metadata": {"application": "customer-support-knowledge-assistant"},
    }]
    result = compare_with_history(current, [], history, [])
    assert not result["endpoint_differences"]  # Missing historical data must not be invented.
    assert any(item["field"] == "run.endpoint" and item["current_value"] == "http://127.0.0.1:11435"
               and item["reason"] == "not_recorded_in_historical_baseline"
               for item in result["uncomparable_fields"])
    assert "not recorded" in result["summary"]


def test_history_comparison_uses_endpoint_captured_on_generation_event():
    from app.investigation import compare_with_history
    current = {"run_id": "bad", "project_id": "p", "scenario": "same", "version": "1", "status": "failed"}
    history = [{"run_id": "good", "project_id": "p", "scenario": "same", "version": "1", "status": "success"}]
    current_events = [{"event_id": "evt_bad", "run_id": "bad", "step": "generation", "event_type": "error",
                       "status": "failed", "error": "connection refused", "payload": {"phase": "error", "llm_endpoint": "http://127.0.0.1:11435"}}]
    prior_events = [{"event_id": "evt_good", "run_id": "good", "step": "generation", "event_type": "generation",
                     "status": "success", "payload": {"phase": "end", "llm_endpoint": "http://127.0.0.1:11434"}}]
    result = compare_with_history(current, current_events, history, prior_events)
    assert result["endpoint_differences"]
    diff = result["endpoint_differences"][0]
    assert diff["current_value"] == "http://127.0.0.1:11435"
    assert diff["historical_value"] == "http://127.0.0.1:11434"
    assert diff["current_event_ids"] == ["evt_bad"]
    assert "evt_good" in diff["historical_event_ids"]


def test_history_comparison_normalizes_endpoint_aliases_across_sdk_versions():
    from app.investigation import compare_with_history
    current = {"run_id": "bad", "project_id": "p", "scenario": "same", "version": "1", "status": "failed",
               "metadata": {"llm_endpoint": "http://127.0.0.1:11435"}}
    history = [{"run_id": "good", "project_id": "p", "scenario": "same", "version": "1", "status": "success",
                "metadata": {"ollama_base_url": "http://127.0.0.1:11434"}}]
    result = compare_with_history(current, [], history, [])
    assert result["endpoint_differences"]
    diff = result["endpoint_differences"][0]
    assert diff["historical_value"] == "http://127.0.0.1:11434"
    assert diff["current_value"] == "http://127.0.0.1:11435"
    assert diff["field"] == "run.endpoint"


def test_history_comparison_normalizes_endpoint_aliases_inside_generation_events():
    from app.investigation import compare_with_history
    current = {"run_id": "bad", "project_id": "p", "scenario": "same", "version": "1", "status": "failed"}
    history = [{"run_id": "good", "project_id": "p", "scenario": "same", "version": "1", "status": "success"}]
    current_events = [{"event_id": "evt_current_generation", "run_id": "bad", "step": "generation", "event_type": "error", "status": "failed",
                       "error": "connection refused", "payload": {"llm_endpoint": "http://127.0.0.1:11435"}}]
    old_events = [{"event_id": "evt_old_generation", "run_id": "good", "step": "generation", "event_type": "generation", "status": "success",
                   "payload": {"ollama_base_url": "http://127.0.0.1:11434"}}]
    result = compare_with_history(current, current_events, history, old_events)
    assert result["endpoint_differences"]
    diff = result["endpoint_differences"][0]
    assert diff["field"] == "generation.endpoint"
    assert diff["current_event_ids"] == ["evt_current_generation"]
    assert "evt_old_generation" in diff["historical_event_ids"]


def test_concatenated_legacy_evidence_ids_are_split_only_into_real_event_ids():
    from app.investigation import normalize_evidence_event_ids
    ids = {
        "evt_b960a525e82843d7952a0dd4af6949f4",
        "evt_840fbfa022244a61b2e84730e593b354",
        "evt_71352f86dea041c8953f6d63bcacba2d",
        "evt_16a031919df04e7ebb024de98c7b42c5",
    }
    joined = "".join(["evt_b960a525e82843d7952a0dd4af6949f4", "evt_840fbfa022244a61b2e84730e593b354",
                      "evt_71352f86dea041c8953f6d63bcacba2d", "evt_16a031919df04e7ebb024de98c7b42c5"])
    assert normalize_evidence_event_ids(joined, ids) == [
        "evt_b960a525e82843d7952a0dd4af6949f4",
        "evt_840fbfa022244a61b2e84730e593b354",
        "evt_71352f86dea041c8953f6d63bcacba2d",
        "evt_16a031919df04e7ebb024de98c7b42c5",
    ]
