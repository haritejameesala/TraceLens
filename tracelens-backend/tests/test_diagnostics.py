from app.diagnostics import diagnose


def event(event_id, event_type, count=None, status="success", step="retrieve"):
    payload = {} if count is None else {"relevant_chunk_count": count}
    return {"event_id": event_id, "event_type": event_type, "payload": payload, "status": status, "step": step}


def test_empty_retrieval_links_baseline_and_current_events():
    findings = diagnose([event("base", "retrieval", 1)], [event("current", "retrieval", 0)])
    finding = next(f for f in findings if f["rule_id"] == "empty_retrieval")
    assert finding["evidence_event_ids"] == ["base", "current"]
    assert finding["severity"] == "high"


def test_relevance_drop_nonzero():
    findings = diagnose([event("base", "retrieval", 3)], [event("current", "retrieval", 1)])
    assert any(f["rule_id"] == "retrieval_relevance_drop" for f in findings)


def test_failed_step_rule():
    findings = diagnose([], [event("error", "error", status="failed", step="generation")])
    assert any(f["rule_id"] == "direct_error" and f["evidence_event_ids"] == ["error"] for f in findings)


def test_no_finding_when_counts_unchanged_and_steps_succeed():
    findings = diagnose([event("base", "retrieval", 2)], [event("current", "retrieval", 2)])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "no_known_rule_triggered"


def test_missing_count_does_not_invent_retrieval_diagnosis():
    findings = diagnose([event("base", "retrieval")], [event("current", "retrieval")])
    assert all(f["rule_id"] != "empty_retrieval" for f in findings)


def test_zero_retrieved_chunks_is_detected_without_inventing_relevance():
    base = event("base", "retrieval", status="success")
    base["payload"] = {"retrieved_chunk_count": 3}
    current = event("current", "retrieval", status="success")
    current["payload"] = {"retrieved_chunk_count": 0}
    finding = next(f for f in diagnose([base], [current]) if f["rule_id"] == "empty_retrieval")
    assert finding["title"] == "No chunks retrieved"
    assert finding["evidence_event_ids"] == ["base", "current"]


def test_retrieved_count_drop_is_not_mislabeled_as_relevance_drop():
    base = event("base", "retrieval")
    base["payload"] = {"retrieved_chunk_count": 5}
    current = event("current", "retrieval")
    current["payload"] = {"retrieved_chunk_count": 2}
    findings = diagnose([base], [current])
    assert any(f["rule_id"] == "retrieval_count_drop" for f in findings)
    assert all(f["rule_id"] != "retrieval_relevance_drop" for f in findings)


def test_classifies_python_syntax_and_import_errors_as_direct_failures():
    from app.diagnostics import diagnose
    for exception_type in ("SyntaxError", "IndentationError", "ModuleNotFoundError", "ImportError"):
        current = [{"event_id": f"evt-{exception_type}", "step": "startup", "event_type": "error",
                    "status": "failed", "error": f"{exception_type}: application could not start",
                    "payload": {"exception_type": exception_type}}]
        finding = next(f for f in diagnose([], current) if f["rule_id"] == "direct_error")
        assert finding["error_category"] == "syntax_or_import"
        assert finding["evidence_event_ids"] == [f"evt-{exception_type}"]


def test_classifies_provider_failure_categories_without_claiming_causality():
    from app.diagnostics import diagnose
    cases = [
        ("HTTP 401 Unauthorized", "authentication"),
        ("HTTP 429 rate limit", "rate_limit"),
        ("HTTP 503 Service Unavailable", "server_error"),
        ("model 'qwen2.5:3b' not found (status code: 404)", "model_unavailable"),
        ("ReadTimeout", "timeout"),
        ("Connection refused", "connection"),
        ("context window exceeded", "context_length"),
        ("JSONDecodeError: invalid JSON", "malformed_output"),
    ]
    for message, expected in cases:
        finding = next(f for f in diagnose([], [{"event_id": "evt", "step": "generation", "event_type": "error",
                                                "status": "failed", "error": message}]) if f["rule_id"] == "direct_error")
        assert finding["error_category"] == expected, (message, finding)
        assert "not proof" in finding["explanation"]


def test_error_text_is_detected_even_when_status_was_not_marked_failed():
    from app.diagnostics import diagnose
    findings = diagnose([], [{"event_id": "evt", "step": "retrieval", "status": "success",
                              "error": "Chroma connection refused"}])
    finding = next(f for f in findings if f["rule_id"] == "direct_error")
    assert finding["error_category"] == "connection"


def test_missing_error_message_is_reported_without_inventing_details():
    from app.diagnostics import diagnose
    finding = next(f for f in diagnose([], [{"event_id": "evt", "step": "generation", "status": "failed"}])
                   if f["rule_id"] == "direct_error")
    assert finding["error_category"] == "unknown"
    assert "without an exception message" in finding["explanation"]


def test_multiple_failures_keep_separate_evidence_ids():
    from app.diagnostics import diagnose
    current = [
        {"event_id": "evt-retrieval", "step": "retrieval", "event_type": "error", "status": "failed", "error": "Chroma connection refused"},
        {"event_id": "evt-generation", "step": "generation", "event_type": "error", "status": "failed", "error": "HTTP 503 Service Unavailable"},
    ]
    findings = [f for f in diagnose([], current) if f["rule_id"] == "direct_error"]
    assert [f["evidence_event_ids"] for f in findings] == [["evt-retrieval"], ["evt-generation"]]
    assert {f["error_category"] for f in findings} == {"connection", "server_error"}
