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
    assert any(f["rule_id"] == "step_failure" and f["evidence_event_ids"] == ["error"] for f in findings)
