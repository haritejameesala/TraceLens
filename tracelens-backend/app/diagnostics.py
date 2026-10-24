"""Deterministic, evidence-linked diagnostics for comparing traced runs."""
def _payload(event):
    value = event.get("payload")
    return value if isinstance(value, dict) else {}

def diagnose(base_events, current_events):
    findings = []
    base = next((e for e in base_events if e.get("event_type") == "retrieval"), None)
    current = next((e for e in current_events if e.get("event_type") == "retrieval"), None)
    if base and current:
        before = _payload(base).get("relevant_chunk_count")
        after = _payload(current).get("relevant_chunk_count")
        if isinstance(before, (int, float)) and isinstance(after, (int, float)) and after < before:
            findings.append({"rule_id":"retrieval_relevance_drop","severity":"critical" if after == 0 else "medium",
                "title":"Retrieval returned fewer relevant chunks",
                "explanation":f"Relevant chunk count changed from {before} to {after}. This is evidence of a retrieval change, not proof that it caused an answer regression.",
                "evidence_event_ids":[base.get("event_id"),current.get("event_id")],
                "recommended_action":"Compare query preprocessing, filters, index version, top-k and score thresholds."})
    for event in current_events:
        if event.get("status") == "failed" or event.get("event_type") == "error":
            findings.append({"rule_id":"step_failure","severity":"high","title":f"Failed step: {event.get('step','unknown')}",
                "explanation":"The current run contains a failed event. Inspect its recorded error and adjacent steps.",
                "evidence_event_ids":[event.get("event_id")],
                "recommended_action":"Inspect the error, inputs, preceding events and the step duration."})
    for event in current_events:
        if event.get("event_type") == "retrieval" and _payload(event).get("relevant_chunk_count") == 0:
            if not any(f["rule_id"] == "retrieval_relevance_drop" for f in findings):
                findings.append({"rule_id":"empty_retrieval","severity":"high","title":"Retrieval returned no chunks",
                    "explanation":"The current retrieval event reports zero relevant chunks.",
                    "evidence_event_ids":[event.get("event_id")],
                    "recommended_action":"Check document ingestion, filters, query text and the retriever score threshold."})
    if not findings:
        findings.append({"rule_id":"no_known_rule_triggered","severity":"info","title":"No known rule triggered",
            "explanation":"The current deterministic rules did not identify a known regression.","evidence_event_ids":[],
            "recommended_action":"Inspect the trace and evaluate answer quality with representative test questions."})
    return findings
