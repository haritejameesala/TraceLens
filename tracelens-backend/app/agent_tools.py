"""Read-only, deterministic tools available to the TraceLens investigation agent.

All tools operate on project-scoped records already loaded by the API. They never
mutate runs, execute user code, or access arbitrary external systems.
"""
from __future__ import annotations
from typing import Any
from app.memory import answer_question, _run_status, _run_time, _parse_time, _duration_summary, redact

TOOL_SPECS = [
    {"name": "selected_run", "description": "Get the selected run's status, timing, metadata, and event summary."},
    {"name": "run_history", "description": "Summarize run outcomes and timestamps before and after the selected run."},
    {"name": "compare_last_success", "description": "Compare the selected run against the latest earlier successful run."},
    {"name": "latency_analysis", "description": "Calculate recorded event-duration statistics and compare with successful history."},
    {"name": "retrieval_analysis", "description": "Inspect recorded retrieval event statuses, errors, durations, and evidence IDs."},
    {"name": "confidence_metrics", "description": "Inspect recorded confidence, relevance, similarity, and reranker metrics."},
    {"name": "failure_analysis", "description": "Summarize recorded exceptions and failed stages for the selected run."},
    {"name": "incident_memories", "description": "Review relevant project-scoped incident memories and their verification status."},
    {"name": "search_events", "description": "Search recorded current and historical event metadata/errors for relevant terms."},
]



def question_needs_agent(question: str, answer_type: str) -> bool:
    """Route genuinely open-ended or multi-part questions through the model planner.

    Exact, measurable questions keep deterministic answers; broad synthesis and
    multi-part questions get the tool-using agent even if a keyword handler matched.
    """
    if answer_type == "general":
        return True
    q = question.lower()
    broad_signals = (
        "pattern", "recommend", "what should", "investigate next", "explain why", "why has",
        "relationship", "related to", "across these", "across runs", "overall", "summarize",
        "possible reasons", "alternative explanation", "what am i missing", "deep dive",
    )
    return any(signal in q for signal in broad_signals)


def _event_safe(ev: dict) -> dict:
    return {k: redact(ev.get(k), 700) if isinstance(ev.get(k), str) else ev.get(k)
            for k in ("event_id", "timestamp", "step", "event_type", "status", "duration_ms", "error",
                      "exception_type", "model", "model_name", "embedding_model", "retrieval_count",
                      "document_count", "confidence", "relevance_score", "similarity_score", "rerank_score")
            if ev.get(k) is not None}


def execute_tool(name: str, run: dict, events: list[dict], memories: list[dict], history: list[dict], query: str = "") -> dict:
    """Execute one allowlisted read-only investigation tool."""
    if name == "selected_run":
        return {"run": {k: redact(run.get(k), 500) if isinstance(run.get(k), str) else run.get(k)
                         for k in ("run_id", "project_id", "status", "created_at", "started_at", "ended_at", "duration_ms", "framework", "name", "version") if run.get(k) is not None},
                "events": [_event_safe(e) for e in events[:100]]}
    if name == "run_history":
        current_time = _parse_time(_run_time(run))
        before, after, undated = [], [], 0
        for item in history:
            r = item.get("run", {})
            when = _parse_time(_run_time(r))
            if not when or not current_time:
                undated += 1
            elif when < current_time:
                before.append(r)
            elif when > current_time:
                after.append(r)
        def summary(items):
            statuses = [_run_status(r) for r in items]
            return {"total": len(items), "successful": statuses.count("success"), "failed": statuses.count("failed"),
                    "other_or_unknown": len(items) - statuses.count("success") - statuses.count("failed")}
        # avoid deriving order from object IDs; order only by recorded timestamp then run_id
        before.sort(key=lambda r: (_parse_time(_run_time(r)), str(r.get("run_id", ""))))
        after.sort(key=lambda r: (_parse_time(_run_time(r)), str(r.get("run_id", ""))))
        return {"before_selected": summary(before), "after_selected": summary(after), "undated_runs_excluded": undated,
                "before_runs": [{"run_id": r.get("run_id"), "status": _run_status(r), "timestamp": _run_time(r)} for r in before[-20:]],
                "after_runs": [{"run_id": r.get("run_id"), "status": _run_status(r), "timestamp": _run_time(r)} for r in after[:20]]}
    if name in {"compare_last_success", "latency_analysis", "retrieval_analysis", "confidence_metrics", "failure_analysis"}:
        questions = {
            "compare_last_success": "What changed compared with the last successful run?",
            "latency_analysis": "Compare latency with previous successful runs.",
            "retrieval_analysis": "Did retrieval fail?",
            "confidence_metrics": "Compare RAG confidence and relevance metrics with previous successful runs.",
            "failure_analysis": "What exact error stopped this run and what stage failed?",
        }
        return answer_question(questions[name], run, events, None, memories, history)
    if name == "incident_memories":
        return {"count": len(memories), "incidents": [{k: redact(m.get(k), 700) if isinstance(m.get(k), str) else m.get(k)
                 for k in ("memory_id", "run_id", "title", "category", "stage", "error_summary", "cause_summary", "outcome", "verified_fix", "signature") if m.get(k) is not None}
                 for m in memories[:10]]}
    if name == "search_events":
        terms = [t.lower() for t in __import__("re").findall(r"[a-zA-Z0-9_.:-]{3,}", query) if t.lower() not in {"what", "when", "where", "which", "this", "that", "with", "from", "have", "were", "does", "about", "runs", "run", "show", "find", "tell", "compare", "could", "would", "should"}]
        records = []
        sources = [(run, events, True)] + [(x.get("run", {}), x.get("events", []), False) for x in history]
        for r, evs, is_current in sources:
            for ev in evs:
                text = " ".join(str(ev.get(k, "")) for k in ("step", "event_type", "status", "error", "exception_type", "model", "model_name", "embedding_model")).lower()
                if not terms or any(term in text for term in terms):
                    records.append({"run_id": r.get("run_id"), "is_selected_run": is_current, **_event_safe(ev)})
                    if len(records) >= 40:
                        break
            if len(records) >= 40:
                break
        return {"query_terms": terms, "matched_events": records, "match_count": len(records)}
    return {"error": f"Unknown tool: {name}"}
