_ERROR_RULES = [
    ("syntax_or_import", ("syntaxerror", "indentationerror", "modulenotfounderror", "importerror"), "Inspect the source file and line; verify syntax, package installation, and the active Python environment."),
    ("authentication", ("401", "unauthorized", "403", "forbidden", "invalid api key", "authentication failed"), "Verify credentials, token scope, and endpoint authentication without exposing secrets."),
    ("rate_limit", ("429", "rate limit", "too many requests", "quota exceeded"), "Check provider quotas and retry policy; use bounded backoff where appropriate."),
    ("server_error", ("500", "502", "503", "504", "internal server error", "bad gateway", "service unavailable"), "Check provider/service health and retryability; distinguish provider errors from local failures."),
    ("context_length", ("context length", "context window", "maximum context", "too many tokens", "token limit exceeded"), "Inspect prompt/context size and model limits; reduce or summarize context before retrying."),
    ("connection", ("connection refused", "connecterror", "connectionerror", "actively refused", "unreachable", "dns resolution", "name or service not known"), "Verify endpoint host/port, DNS, service availability, and network reachability."),
    ("timeout", ("timeout", "timed out", "deadline exceeded", "readtimeout", "connecttimeout"), "Check stage latency, service load, timeout settings, and retryability."),
    ("model_unavailable", ("model not found", "model unavailable", "no such model", "http 404", "status code: 404"), "Verify the exact model identifier is installed or available at the configured endpoint."),
    ("retrieval", ("retrieval", "vector store", "chroma", "embedding", "collection not found", "index not found", "reranker"), "Inspect vector-store connectivity, collection/index names, embedding compatibility, filters, and reranker configuration."),
    ("malformed_output", ("jsondecodeerror", "validationerror", "invalid json", "malformed output", "unexpected token"), "Inspect the output schema and parser error; validate model output before downstream use."),
]


def classify_error(event: dict) -> dict:
    """Classify a recorded exception; this is a hint, not proof of root cause."""
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    exception_type = str(payload.get("exception_type") or event.get("exception_type") or "")
    message = str(event.get("error") or event.get("message") or "")
    text = f"{exception_type} {message}".lower()
    for category, patterns, recommendation in _ERROR_RULES:
        if any(pattern in text for pattern in patterns):
            return {"category": category, "exception_type": exception_type or None, "recommendation": recommendation}
    return {"category": "unknown", "exception_type": exception_type or None,
            "recommendation": "Inspect the recorded exception and surrounding events; no known signature matched."}


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
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        is_failed = str(event.get("status", "")).lower() in {"failed", "failure", "error"} or bool(event.get("error")) or event.get("event_type") == "error"
        if is_failed:
            event_id = event.get("event_id")
            classification = classify_error(event)
            summary = str(event.get("error") or payload.get("exception_type") or "failure status recorded without an exception message")[:500]
            findings.append({
                "rule_id": "direct_error", "severity": "high",
                "title": f"{classification['category'].replace('_', ' ').title()} at {event.get('step', 'unknown')}",
                "explanation": f"Recorded failure evidence: {summary}. Classified as {classification['category']}; classification is a diagnostic hint, not proof of an upstream cause.",
                "error_category": classification["category"],
                "exception_type": classification["exception_type"],
                "evidence_event_ids": [event_id] if event_id else [],
                "recommended_action": classification["recommendation"],
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
