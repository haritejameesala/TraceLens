## 0.5.4
- Package version aligned with TraceLens 0.5.4 clarity/reporting release. No SDK API break introduced in this release.

## 0.5.2

- Compatible with history-first, stage-aware investigation and sanitized application run metadata.

# Changelog

## 0.5.0 — Structured telemetry and investigation context

- Added privacy-preserving `record_retrieval` and `record_generation` helpers for retrieval counts, query fingerprints, safe chunk references, model metadata, latency, token usage, and finish reasons.
- Added trace identifiers to lifecycle, custom, retrieval, generation, and step events.
- Added SDK/Python/platform metadata to the run-start event.
- Expanded LangChain callback telemetry with retriever metadata, available relevance scores, model names, token usage, and root-run correlation.
- Fixed the backend event schema to accept SDK `running` start events and additive trace-correlation fields.
- Improved deterministic RCA for connection refusal: it identifies a recorded endpoint when available, distinguishes observed failure from likely causes, includes the immediately preceding event as context, and keeps the full ordered timeline.
- Improved RCA context assembly and credential-pattern redaction for string values.
- Added regression tests for privacy-preserving telemetry and connection-refused diagnosis.


## 0.4.0 — SDK toolkit and lifecycle hardening

- Added `traced_step` decorator for custom Python callables.
- `trace_step` now emits explicit start and terminal events with a stable step ID.
- Added best-effort recursive payload redaction for secret-like keys and common token patterns.
- Failure events record bounded stack-frame metadata instead of serializing local-variable-bearing tracebacks.
- Added public API documentation, security guidance, a working custom RAG sample, and privacy/decorator tests.
- Added development/test optional dependencies and pytest configuration.

### Compatibility note

This release adds a start event for every `trace_step`; dashboards and diagnostic rules should tolerate these additional events. The existing terminal event name remains the original step name.

## 0.5.3

- Continues attaching explicitly supplied sanitized LLM endpoint/model metadata to run metadata and supported LangChain stage events for history-first comparisons.
- Pair with the 0.5.3 backend to normalize legacy endpoint/model field names across historical SDK versions.
