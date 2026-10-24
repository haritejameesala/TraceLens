def diagnose(base_events, current_events):
    """Deterministic, evidence-linked rules. Findings do not claim causality."""
    findings = []
    base_retrieval = next((e for e in base_events if e.get("event_type") == "retrieval"), None)
    current_retrieval = next((e for e in current_events if e.get("event_type") == "retrieval"), None)

    if current_retrieval:
        payload = current_retrieval.get("payload", {})
        count = payload.get("relevant_chunk_count")
        if isinstance(count, (int, float)) and count == 0:
            evidence = [current_retrieval["event_id"]]
            if base_retrieval:
                evidence.insert(0, base_retrieval["event_id"])
            findings.append({
                "rule_id": "empty_retrieval",
                "severity": "high" if base_retrieval and base_retrieval.get("payload", {}).get("relevant_chunk_count", 0) > 0 else "medium",
                "title": "No relevant chunks retrieved",
                "explanation": "The current retrieval event reports zero relevant chunks. This indicates a retrieval-quality problem, not necessarily a program crash.",
                "evidence_event_ids": evidence,
                "recommended_action": "Inspect the query, corpus, filters, index state, and retrieval thresholds.",
            })

    if base_retrieval and current_retrieval:
        before = base_retrieval.get("payload", {}).get("relevant_chunk_count")
        after = current_retrieval.get("payload", {}).get("relevant_chunk_count")
        if isinstance(before, (int, float)) and isinstance(after, (int, float)) and after < before:
            # Avoid duplicate findings for the exact same zero-result condition.
            if after != 0:
                findings.append({
                    "rule_id": "retrieval_relevance_drop",
                    "severity": "high" if before > 0 and after == 0 else "medium",
                    "title": "Retrieval returned fewer relevant chunks",
                    "explanation": f"Relevant chunk count dropped from {before} to {after}; suspicious, but not proof of causality.",
                    "evidence_event_ids": [base_retrieval["event_id"], current_retrieval["event_id"]],
                    "recommended_action": "Inspect retriever filters, query preprocessing, index version, and similarity threshold.",
                })

    for event in current_events:
        if event.get("status") == "failed":
            findings.append({
                "rule_id": "step_failure", "severity": "high",
                "title": f"Failed step: {event.get('step', 'unknown')}",
                "explanation": "An instrumented step failed in the current run.",
                "evidence_event_ids": [event["event_id"]],
                "recommended_action": "Inspect the recorded error and the step's safe metadata.",
            })

    if not findings:
        findings.append({
            "rule_id": "no_known_rule_triggered", "severity": "info",
            "title": "No known rule triggered",
            "explanation": "The current deterministic rules did not identify a likely issue.",
            "evidence_event_ids": [],
            "recommended_action": "Inspect the trace and add domain-specific diagnostic rules if needed.",
        })
    return findings
