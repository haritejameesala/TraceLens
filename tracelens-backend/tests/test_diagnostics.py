from app.diagnostics import diagnose

def event(event_id, event_type="retrieval", status="success", count=2, step="retrieve"):
    return {"event_id":event_id,"event_type":event_type,"status":status,"step":step,"payload":{"relevant_chunk_count":count}}

def test_retrieval_drop_has_both_evidence_ids():
    findings = diagnose([event("before", count=4)], [event("after", count=0)])
    finding = next(item for item in findings if item["rule_id"] == "retrieval_relevance_drop")
    assert finding["severity"] == "critical"
    assert finding["evidence_event_ids"] == ["before", "after"]
    assert "not proof" in finding["explanation"]

def test_failed_event_is_reported():
    assert any(item["rule_id"] == "step_failure" for item in diagnose([], [event("err", "error", "failed", step="generate")]))

def test_empty_retrieval_without_baseline_is_reported():
    assert any(item["rule_id"] == "empty_retrieval" for item in diagnose([], [event("empty", count=0)]))

def test_no_trigger_returns_info_finding():
    findings = diagnose([event("a")], [event("b")])
    assert len(findings) == 1 and findings[0]["severity"] == "info"
