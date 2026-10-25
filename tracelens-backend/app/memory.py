"""Project-scoped incident memory helpers for TraceLens.

Memory records contain redacted summaries and references, not raw prompts or payloads.
Similarity is intentionally transparent and deterministic for the first implementation.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

# Redaction regexes
_SECRET = re.compile(r"(?i)(api[_-]?key|access[_-]?token|token|password|secret|authorization)\s*[:=]\s*[^\s,;\u0026]+")
_BEARER = re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+")
_URL = re.compile(r"https?://[^\s'\"`]+", re.I)


def redact(text: Any, limit: int = 1200) -> str:
    """Redact common credentials before incident summaries are persisted."""
    value = str(text or "")
    value = _BEARER.sub(r"\\1[REDACTED]", value)
    value = _SECRET.sub(r"\\1=[REDACTED]", value)
    value = re.sub(r"(?i)([?\u0026](?:api[_-]?key|access[_-]?token|token|secret|password)=)[^\u0026\\s]+", r"\\1[REDACTED]", value)
    return value[:max(0, limit)]


def error_signature(run: dict, events: list[dict], report: dict) -> dict:
    failed = next((e for e in events if e.get("status") == "failed" or e.get("error") or e.get("event_type") == "error"), {})
    error = redact(failed.get("error") or report.get("title") or report.get("likely_cause"), 500)
    classification_text = error.lower()
    normalized = _URL.sub("<url>", classification_text)
    normalized = re.sub(r"\\b\\d{2,}\\b", "<n>", normalized)
    normalized = re.sub(r"\\s+", " ", normalized).strip()
    category = "unknown"
    for label, patterns in {
        "syntax_or_import": ("syntaxerror", "indentationerror", "modulenotfounderror", "importerror"),
        "authentication": ("http 401", "status code: 401", "unauthorized", "http 403", "status code: 403", "forbidden", "invalid api key", "authentication failed"),
        "rate_limit": ("rate limit", "too many requests", "429", "quota exceeded"),
        "server_error": ("http 500", "http 502", "http 503", "http 504", "status code: 500", "status code: 502", "status code: 503", "status code: 504", "internal server error", "bad gateway", "service unavailable"),
        "context_length": ("context length", "context window", "maximum context", "too many tokens", "token limit exceeded"),
        "connection": ("connection refused", "connecterror", "connectionerror", "actively refused", "unreachable", "name or service not known", "dns resolution"),
        "timeout": ("timeout", "timed out", "deadline exceeded", "readtimeout", "connecttimeout"),
        "retrieval": ("retrieval", "vector store", "chroma", "embedding", "no documents", "collection not found", "index not found", "reranker"),
        "model": ("model not found", "ollama", "model unavailable", "status code: 404", "http 404"),
        "malformed_output": ("jsondecodeerror", "validationerror", "invalid json", "malformed output", "unexpected token"),
    }.items():
        if any(pattern in classification_text for pattern in patterns):
            category = label
            break
    stage = redact(failed.get("step") or failed.get("event_type") or "unknown", 120)
    signature = hashlib.sha256(f"{category}|{stage.lower()}|{normalized}".encode()).hexdigest()[:24]
    return {
        "signature": signature,
        "category": category,
        "stage": stage,
        "error_summary": error,
        "title": redact(report.get("title"), 200),
        "cause_summary": redact(report.get("likely_cause"), 1200),
    }


def memory_match_score(current: dict, past: dict) -> int:
    score = 0
    if current.get("signature") and current.get("signature") == past.get("signature"):
        score += 5
    category = str(current.get("category", "unknown")).lower()
    past_category = str(past.get("category", "unknown")).lower()
    if category != "unknown" and category == past_category:
        score += 2
    stage = str(current.get("stage", "unknown")).lower()
    past_stage = str(past.get("stage", "unknown")).lower()
    if stage not in {"", "unknown"} and stage == past_stage:
        score += 2
    return score

# Helper functions required by agent_tools

def _run_status(run: dict) -> str:
    """Return the status of a run, defaulting to ``"unknown"``."""
    return str(run.get("status", "unknown"))


def _run_time(run: dict) -> str | None:
    """Return a timestamp for the run.
    Prefers ``started_at`` then ``created_at``.
    """
    return run.get("started_at") or run.get("created_at")


def _parse_time(ts: str | None) -> datetime | None:
    """Parse an ISO‑8601 string to ``datetime``.
    Returns ``None`` on failure.
    """
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.rstrip("Z"))
    except Exception:
        return None


def _duration_summary(run: dict) -> dict:
    """Return a simple duration summary for a run.
    ``seconds`` is a float or ``None``; ``human`` is a readable string.
    """
    start = _parse_time(run.get("started_at"))
    end = _parse_time(run.get("ended_at"))
    secs = (end - start).total_seconds() if start and end else None
    return {"seconds": secs, "human": f"{secs:.1f}s" if secs is not None else None}


def answer_question(question: str, run: dict, events: list[dict], extra: dict | None, memories: list[dict], history: list[dict]) -> dict:
    """Placeholder deterministic answer for tests.
    Returns a minimal dict with an ``answer`` field.
    """
    return {"answer": f"Placeholder answer for: {question}"}
