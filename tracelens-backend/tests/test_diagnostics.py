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
