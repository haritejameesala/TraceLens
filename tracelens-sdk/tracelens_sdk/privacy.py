"""Best-effort payload sanitization helpers for TraceLens SDK."""
from __future__ import annotations
import re
from typing import Any

_SENSITIVE_KEY = re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|authorization|cookie|credential|private[_-]?key|card[_-]?number|ssn)")
_SENSITIVE_TEXT = [
    (re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(api[_-]?key|access[_-]?token|secret|password|token)(\s*[:=]\s*)[^\s,;]+"), r"\1\2[REDACTED]"),
    (re.compile(r"(?i)sk-[A-Za-z0-9_-]{12,}"), "[REDACTED_KEY]"),
]

def sanitize_text(value: str) -> str:
    result = str(value)
    for pattern, replacement in _SENSITIVE_TEXT:
        result = pattern.sub(replacement, result)
    return result

def sanitize_payload(value: Any, *, max_depth: int = 8, _depth: int = 0) -> Any:
    """Recursively redact secret-like keys and strings; truncate oversized strings.

    This is a safety net, not a guarantee that arbitrary personal data is detected.
    Applications should still send only the metadata needed for observability.
    """
    if _depth > max_depth:
        return "[MAX_DEPTH]"
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            key_str = str(key)[:120]
            clean[key_str] = "[REDACTED]" if _SENSITIVE_KEY.search(key_str) else sanitize_payload(item, max_depth=max_depth, _depth=_depth + 1)
        return clean
    if isinstance(value, (list, tuple)):
        return [sanitize_payload(item, max_depth=max_depth, _depth=_depth + 1) for item in value[:500]]
    if isinstance(value, str):
        return sanitize_text(value[:4000])
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:500]
