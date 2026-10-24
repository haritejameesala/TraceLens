def _count(event, key):
    value = (event or {}).get("payload", {}).get(key)
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def diagnose(base_events, current_events):
    """Apply deterministic diagnostics with evidence IDs from supplied events.

    Relevant-chunk counts are used only when explicitly supplied. Raw retrieved
    counts can prove empty retrieval, but are not treated as relevance judgments.
    Findings indicate symptoms, not causal root-cause proof.
    """
    findings = []
    base_retrieval = next((e for e in reversed(base_events) if e.get("event_type") == "retrieval" and e.get("payload", {}).get("phase", "end") == "end"), None)
    current_retrieval = next((e for e in reversed(current_events) if e.get("event_type") == "retrieval" and e.get("payload", {}).get("phase", "end") == "end"), None)

    if current_retrieval:
        current_relevant = _count(current_retrieval, "relevant_chunk_count")
        current_retrieved = _count(current_retrieval, "retrieved_chunk_count")
        is_empty = current_relevant == 0 or current_retrieved == 0
        if is_empty:
            baseline_relevant = _count(base_retrieval, "relevant_chunk_count")
            baseline_retrieved = _count(base_retrieval, "retrieved_chunk_count")
            baseline_positive = (baseline_relevant is not None and baseline_relevant > 0) or (baseline_retrieved is not None and baseline_retrieved > 0)
            evidence = []
            if base_retrieval:
                evidence.append(base_retrieval.get("event_id"))
            evidence.append(current_retrieval.get("event_id"))
            evidence = [event_id for event_id in evidence if event_id]
            if current_retrieved == 0:
                title = "No chunks retrieved"
                explanation = "The current retrieval event reports zero retrieved chunks. This is an empty-retrieval symptom, not proof of the underlying cause."
            else:
                title = "No relevant chunks retrieved"
                explanation = "The current retrieval event explicitly reports zero relevant chunks. This indicates a retrieval-quality problem, not necessarily a program crash."
            findings.append({
                "rule_id": "empty_retrieval",
                "severity": "high" if base_retrieval and baseline_positive else "medium",
                "title": title,
                "explanation": explanation,
                "evidence_event_ids": evidence,
                "recommended_action": "Inspect the query, corpus, filters, index state, and retrieval thresholds.",
            })

    if base_retrieval and current_retrieval:
        # Compare relevance only when both runs carry explicit relevance counts.
        before_rel = _count(base_retrieval, "relevant_chunk_count")
        after_rel = _count(current_retrieval, "relevant_chunk_count")
        before_ret = _count(base_retrieval, "retrieved_chunk_count")
        after_ret = _count(current_retrieval, "retrieved_chunk_count")
        metric = "relevant" if before_rel is not None and after_rel is not None else "retrieved" if before_ret is not None and after_ret is not None else None
        before, after = (before_rel, after_rel) if metric == "relevant" else (before_ret, after_ret)
        if metric and before is not None and after is not None and after < before and after != 0:
            findings.append({
                "rule_id": "retrieval_relevance_drop" if metric == "relevant" else "retrieval_count_drop",
                "severity": "medium",
                "title": "Retrieval returned fewer relevant chunks" if metric == "relevant" else "Retrieval returned fewer chunks",
                "explanation": f"{metric.capitalize()} chunk count dropped from {before} to {after}; suspicious, but not proof of causality.",
                "evidence_event_ids": [base_retrieval["event_id"], current_retrieval["event_id"]],
                "recommended_action": "Inspect retriever filters, query preprocessing, index version, and similarity threshold.",
            })

    for event in current_events:
        if event.get("status") == "failed":
            event_id = event.get("event_id")
            findings.append({
                "rule_id": "step_failure", "severity": "high",
                "title": f"Failed step: {event.get('step', 'unknown')}",
                "explanation": "An instrumented step failed in the current run.",
                "evidence_event_ids": [event_id] if event_id else [],
                "recommended_action": "Inspect the recorded error and the step's safe metadata.",
            })

    if not findings:
        findings.append({
            "rule_id": "no_known_rule_triggered", "severity": "info",
            "title": "No known rule triggered",
            "explanation": "The current deterministic rules did not identify a likely issue. This is not a guarantee that the run is correct.",
            "evidence_event_ids": [],
            "recommended_action": "Inspect the trace and add domain-specific diagnostic rules if needed.",
        })
    return findings
