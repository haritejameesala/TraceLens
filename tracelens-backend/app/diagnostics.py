def diagnose(base_events, current_events):
    findings = []
    base = next((e for e in base_events if e.get("event_type") == "retrieval"), None)
    current = next((e for e in current_events if e.get("event_type") == "retrieval"), None)
    if base and current:
        before = base.get("payload", {}).get("relevant_chunk_count")
        after = current.get("payload", {}).get("relevant_chunk_count")
        if isinstance(before, (int, float)) and isinstance(after, (int, float)) and after < before:
            findings.append({
                "rule_id": "retrieval_relevance_drop", "severity": "high" if after == 0 else "medium",
                "title": "Retrieval returned fewer relevant chunks",
                "explanation": f"Relevant chunk count dropped from {before} to {after}; suspicious, but not proof of causality.",
                "evidence_event_ids": [base["event_id"], current["event_id"]],
                "recommended_action": "Inspect retriever filters, query preprocessing, index version, and similarity threshold."
            })
    for e in current_events:
        if e.get("status") == "failed":
            findings.append({"rule_id":"step_failure","severity":"high","title":f"Failed step: {e.get('step')}",
                "explanation":"An event failed in the current run.","evidence_event_ids":[e["event_id"]],
                "recommended_action":"Inspect the recorded error and inputs."})
    if not findings:
        findings.append({"rule_id":"no_known_rule_triggered","severity":"info","title":"No known rule triggered",
            "explanation":"Current diagnostic rules did not identify a likely cause.","evidence_event_ids":[],
            "recommended_action":"Inspect the trace and add domain-specific rules."})
    return findings
