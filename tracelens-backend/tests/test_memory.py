from app.memory import error_signature, memory_match_score, redact


def test_error_signature_groups_same_connection_failure_and_redacts_secrets():
    run = {"run_id": "r1", "status": "failed"}
    events = [{"event_id": "e1", "step": "generation", "event_type": "error", "status": "failed",
               "error": "Connection refused at http://localhost:11435 api_key=supersecret"}]
    report = {"title": "Connection refused", "likely_cause": "Generation could not connect"}
    signature = error_signature(run, events, report)
    assert signature["category"] == "connection"
    assert "supersecret" not in signature["error_summary"]
    same = error_signature(run, [{**events[0], "event_id": "e2"}], report)
    assert signature["signature"] == same["signature"]


def test_memory_match_prioritizes_matching_signature_and_stage():
    current = {"signature": "abc", "category": "connection", "stage": "generation"}
    assert memory_match_score(current, {**current}) == 9
    assert memory_match_score(current, {"signature": "other", "category": "retrieval", "stage": "retriever"}) == 0


def test_unknown_memory_signature_does_not_match_every_unknown_incident():
    current = {"signature": "current", "category": "unknown", "stage": "unknown"}
    past = {"signature": "past", "category": "unknown", "stage": "unknown"}
    assert memory_match_score(current, past) == 0


def test_redaction_masks_bearer_tokens_and_url_query_secrets():
    raw = "Authorization: Bearer abc.def.ghi https://example.test/run?api_key=supersecret&x=1"
    safe = redact(raw)
    assert "abc.def.ghi" not in safe
    assert "supersecret" not in safe
    assert "[REDACTED]" in safe


def test_error_signature_classifies_common_provider_errors():
    cases = [
        ("HTTP 401 Unauthorized", "authentication"),
        ("HTTP 429 rate limit exceeded", "rate_limit"),
        ("HTTP 503 Service Unavailable", "server_error"),
        ("model 'qwen2.5:3b' not found (status code: 404)", "model"),
        ("ReadTimeout while calling generation", "timeout"),
        ("ModuleNotFoundError: No module named 'fake_package'", "syntax_or_import"),
        ("JSONDecodeError: malformed output", "malformed_output"),
    ]
    for message, expected in cases:
        result = error_signature({}, [{"step": "generation", "status": "failed", "error": message}], {})
        assert result["category"] == expected, (message, result)


def test_error_signature_normalizes_variable_ports_and_numbers():
    first = error_signature({}, [{"step": "generation", "status": "failed", "error": "Connection refused http://localhost:11434 after 123 ms"}], {})
    second = error_signature({}, [{"step": "generation", "status": "failed", "error": "Connection refused http://localhost:11435 after 456 ms"}], {})
    assert first["signature"] == second["signature"]


def test_redaction_limit_is_respected():
    assert len(redact("x" * 50, limit=12)) == 12
    assert redact("secret=abc", limit=0) == ""
