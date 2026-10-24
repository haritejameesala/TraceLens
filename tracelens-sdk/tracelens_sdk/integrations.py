"""Optional framework integrations for automatic TraceLens instrumentation.

Install with ``pip install 'tracelens-sdk[langchain]'``. This callback captures
supported LangChain callback boundaries; arbitrary Python functions still need
manual hooks or a custom integration. Payload capture is deliberately minimal.
"""
from __future__ import annotations
from time import perf_counter
import hashlib
from typing import Any

try:
    from langchain_core.callbacks import BaseCallbackHandler
except ImportError as exc:  # pragma: no cover - depends on optional extra
    raise ImportError("LangChain integration requires: pip install 'tracelens-sdk[langchain]'") from exc


class TraceLensCallbackHandler(BaseCallbackHandler):
    """Automatically record a root LangChain invocation and its callback events."""
    raise_error = False
    run_inline = True

    def __init__(self, tracer, run_name: str = "langchain-invocation", version: str = "dev", metadata: dict[str, Any] | None = None):
        self.tracer = tracer
        self.run_name = run_name
        self.version = version
        self.metadata = metadata or {}
        self._trace_run = None
        self._root_id = None
        self._started: dict[str, float] = {}
        self._failed = False
        # Callback providers may retry notifications. Suppress duplicate lifecycle
        # boundaries by framework run ID + operation + phase.
        self._seen_callbacks: set[tuple[str, str, str]] = set()

    def _claim_callback(self, run_id, operation: str, phase: str) -> bool:
        key = (self._id(run_id) or "unknown", operation, phase)
        if key in self._seen_callbacks:
            return False
        self._seen_callbacks.add(key)
        return True

    @staticmethod
    def _id(value):
        return str(value) if value is not None else None

    def _event(self, step, event_type, run_id, parent_run_id=None, status="success", extra=None, error=None):
        if self._trace_run is None:
            return
        payload = {"framework": "langchain", "framework_run_id": self._id(run_id)}
        # Attach sanitized operational configuration to each stage event as well as
        # run metadata. This makes generation-stage history comparable and avoids
        # depending on run-level metadata being fetched by downstream consumers.
        for key in ("llm_endpoint", "llm_model", "embedding_model", "retrieval_k", "environment", "application", "config_fingerprint", "configuration_fingerprint"):
            value = self.metadata.get(key)
            if value is not None and isinstance(value, (str, int, float, bool)):
                payload[key] = str(value)[:300] if isinstance(value, str) else value
        if self._root_id is not None:
            payload["root_framework_run_id"] = self._root_id
        if parent_run_id is not None:
            payload["parent_run_id"] = self._id(parent_run_id)
        if extra:
            payload.update(extra)
        phase = (extra or {}).get("phase")
        started = self._started.get(self._id(run_id))
        duration = None
        if phase != "start":
            started = self._started.pop(self._id(run_id), None)
            duration = round((perf_counter() - started) * 1000, 3) if started is not None else None
        from .events import TraceEvent
        self._trace_run.record_event(TraceEvent(step=step[:120], event_type=event_type, status=status,
            payload=payload, duration_ms=duration, error=(str(error)[:1000] if error else None),
            trace_id=self._trace_run.trace_id))

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs):
        if not self._claim_callback(run_id, "chain", "start"):
            return
        rid = self._id(run_id)
        self._started[rid] = perf_counter()
        if parent_run_id is None:
            self._root_id = rid
            name = kwargs.get("name") or (serialized or {}).get("name") or self.run_name
            self._trace_run = self.tracer.start_run(str(name)[:150], version=self.version,
                metadata={**self.metadata, "framework": "langchain"})
            self._trace_run.__enter__()
        safe_inputs = list(inputs.keys())[:50] if isinstance(inputs, dict) else []
        self._event((serialized or {}).get("name") or "chain", "custom", run_id, parent_run_id,
                    extra={"phase": "start", "input_keys": safe_inputs, "operation": "chain"})

    def on_chain_end(self, outputs, *, run_id, parent_run_id=None, **kwargs):
        if not self._claim_callback(run_id, "chain", "end"):
            return
        self._event("chain", "custom", run_id, parent_run_id, extra={"phase": "end", "output_keys": list(outputs.keys())[:50] if isinstance(outputs, dict) else []})
        if self._id(run_id) == self._root_id and self._trace_run is not None:
            self._trace_run.__exit__(None, None, None)
            self._trace_run = None
            self._root_id = None

    def on_chain_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        if not self._claim_callback(run_id, "chain", "error"):
            return
        self._failed = True
        self._event("chain", "error", run_id, parent_run_id, status="failed", error=error, extra={"phase": "error", "exception_type": type(error).__name__})
        if self._id(run_id) == self._root_id and self._trace_run is not None:
            self._trace_run.__exit__(type(error), error, getattr(error, "__traceback__", None))
            self._trace_run = None
            self._root_id = None

    def on_retriever_start(self, serialized, query, *, run_id, parent_run_id=None, **kwargs):
        if not self._claim_callback(run_id, "retrieval", "start"):
            return
        self._started[self._id(run_id)] = perf_counter()
        self._event((serialized or {}).get("name") or "retriever", "custom", run_id, parent_run_id,
                    extra={"phase": "start", "operation": "retrieval", "query_length": len(query) if isinstance(query, str) else None})

    def on_retriever_end(self, documents, *, run_id, parent_run_id=None, **kwargs):
        if not self._claim_callback(run_id, "retrieval", "end"):
            return
        docs = documents if isinstance(documents, (list, tuple)) else []
        sources = []
        chunk_ids = []
        for doc in docs[:50]:
            metadata = getattr(doc, "metadata", {}) or {}
            source = metadata.get("source")
            chunk_id = metadata.get("chunk_id")
            if source is not None:
                sources.append(str(source)[:300])
            if chunk_id is not None:
                chunk_ids.append(str(chunk_id)[:120])
        scores = []
        for doc in docs[:50]:
            metadata = getattr(doc, "metadata", {}) or {}
            score = metadata.get("score", metadata.get("relevance_score"))
            if isinstance(score, (int, float)) and not isinstance(score, bool):
                scores.append({"rank": len(scores) + 1, "score": float(score),
                               "source": str(metadata.get("source", ""))[:300]})
        self._event("retriever", "retrieval", run_id, parent_run_id,
                    extra={"phase": "end", "retrieved_chunk_count": len(docs),
                           "source_files": sorted(set(sources))[:50], "chunk_ids": chunk_ids,
                           "available_relevance_scores": scores})

    def on_retriever_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        if not self._claim_callback(run_id, "retrieval", "error"):
            return
        self._event("retriever", "error", run_id, parent_run_id, status="failed", error=error, extra={"phase": "error"})

    def on_llm_start(self, serialized, prompts, *, run_id, parent_run_id=None, **kwargs):
        if not self._claim_callback(run_id, "generation", "start"):
            return
        self._started[self._id(run_id)] = perf_counter()
        model_name = (serialized or {}).get("kwargs", {}).get("model") or (serialized or {}).get("kwargs", {}).get("model_name")
        self._event((serialized or {}).get("name") or "llm", "generation", run_id, parent_run_id,
                    extra={"phase": "start", "prompt_count": len(prompts) if prompts else 0,
                           "model": str(model_name)[:160] if model_name else None, "operation": "generation"})

    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kwargs):
        if not self._claim_callback(run_id, "generation", "start"):
            return
        self._started[self._id(run_id)] = perf_counter()
        model_name = (serialized or {}).get("kwargs", {}).get("model") or (serialized or {}).get("kwargs", {}).get("model_name")
        self._event((serialized or {}).get("name") or "chat_model", "generation", run_id, parent_run_id,
                    extra={"phase": "start", "message_batch_count": len(messages) if messages else 0,
                           "model": str(model_name)[:160] if model_name else None, "operation": "generation"})

    def on_llm_end(self, response, *, run_id, parent_run_id=None, **kwargs):
        if not self._claim_callback(run_id, "generation", "end"):
            return
        payload = {"phase": "end"}
        usage = getattr(getattr(response, "llm_output", None), "get", lambda *_: None)("token_usage")
        if isinstance(usage, dict):
            safe_usage = {str(k)[:80]: v for k, v in usage.items()
                          if isinstance(v, (int, float)) and not isinstance(v, bool)}
            if safe_usage:
                payload["token_usage"] = safe_usage
        response_metadata = getattr(response, "llm_output", None)
        if isinstance(response_metadata, dict):
            for source_key, target_key in (("model_name", "model"), ("model", "model"), ("finish_reason", "finish_reason")):
                value = response_metadata.get(source_key)
                if isinstance(value, (str, int, float)):
                    payload[target_key] = str(value)[:160]
        self._event("generation", "generation", run_id, parent_run_id, extra=payload)

    def on_llm_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        if not self._claim_callback(run_id, "generation", "error"):
            return
        self._event("generation", "error", run_id, parent_run_id, status="failed", error=error, extra={"phase": "error"})
