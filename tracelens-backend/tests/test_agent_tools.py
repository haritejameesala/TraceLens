from app.agent_tools import TOOL_SPECS, execute_tool


def test_agent_tools_are_read_only_and_allowlisted():
    names = {item["name"] for item in TOOL_SPECS}
    assert {"selected_run", "run_history", "compare_last_success", "latency_analysis",
            "retrieval_analysis", "confidence_metrics", "failure_analysis", "incident_memories", "search_events"} <= names
    result = execute_tool("unknown_tool", {"run_id": "r"}, [], [], [])
    assert "error" in result


def test_run_history_tool_counts_success_and_failure_before_and_after():
    run = {"run_id": "current", "project_id": "p", "status": "failed", "created_at": "2026-01-03T00:00:00Z"}
    history = [
        {"run": {"run_id": "a", "status": "success", "created_at": "2026-01-01T00:00:00Z"}, "events": []},
        {"run": {"run_id": "b", "status": "failed", "created_at": "2026-01-02T00:00:00Z"}, "events": []},
        {"run": {"run_id": "c", "status": "success", "created_at": "2026-01-04T00:00:00Z"}, "events": []},
    ]
    result = execute_tool("run_history", run, [], [], history)
    assert result["before_selected"] == {"total": 2, "successful": 1, "failed": 1, "other_or_unknown": 0}
    assert result["after_selected"] == {"total": 1, "successful": 1, "failed": 0, "other_or_unknown": 0}


def test_search_events_finds_historical_error_and_keeps_run_reference():
    run = {"run_id": "current", "status": "failed"}
    history = [{"run": {"run_id": "past"}, "events": [
        {"event_id": "evt-past", "step": "generation", "status": "failed", "error": "model not found"}
    ]}]
    result = execute_tool("search_events", run, [], [], history, "model not found")
    assert result["match_count"] == 1
    assert result["matched_events"][0]["event_id"] == "evt-past"
    assert result["matched_events"][0]["run_id"] == "past"


def test_selected_run_tool_returns_only_allowlisted_event_fields():
    result = execute_tool("selected_run", {"run_id": "r1", "status": "failed"}, [
        {"event_id": "evt1", "step": "generation", "error": "failed", "payload": {"customer_prompt": "private"}}
    ], [], [])
    assert result["events"][0]["event_id"] == "evt1"
    assert "payload" not in result["events"][0]


def test_open_ended_multi_part_question_uses_agent_even_if_keyword_handler_matches():
    from app.agent_tools import question_needs_agent
    assert question_needs_agent("Why has latency increased and what should I investigate next?", "latency")
    assert question_needs_agent("What patterns do you notice across these runs?", "general")
    assert not question_needs_agent("Compare latency with previous successful runs", "latency")
