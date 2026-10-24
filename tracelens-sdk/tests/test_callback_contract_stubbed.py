"""Exercise callback logic without installing the optional LangChain extra.

These tests validate TraceLens' callback protocol, not compatibility with every
real LangChain release. The optional dependency integration suite remains separate.
"""
import importlib
import sys
import types
from uuid import uuid4

callbacks_module = types.ModuleType("langchain_core.callbacks")
callbacks_module.BaseCallbackHandler = type("BaseCallbackHandler", (), {})
langchain_module = types.ModuleType("langchain_core")
langchain_module.__path__ = []
sys.modules.setdefault("langchain_core", langchain_module)
sys.modules["langchain_core.callbacks"] = callbacks_module
integration_module = importlib.import_module("tracelens_sdk.integrations")
# Remove the temporary stubs so the real optional-integration tests can correctly skip
# when LangChain is not installed in this environment. The imported module keeps its base class.
sys.modules.pop("langchain_core.callbacks", None)
sys.modules.pop("langchain_core", None)


class FakeRun:
    def __init__(self):
        self.events = []
        self.trace_id = f"trace-{uuid4().hex}"
        self.exit_calls = []
    def __enter__(self):
        return self
    def record_event(self, event):
        self.events.append(event)
    def __exit__(self, *args):
        self.exit_calls.append(args)


class FakeTracer:
    def __init__(self):
        self.runs = []
    def start_run(self, *args, **kwargs):
        run = FakeRun()
        self.runs.append(run)
        return run


def test_duplicate_callback_notifications_do_not_duplicate_events_or_runs():
    tracer = FakeTracer()
    callback = integration_module.TraceLensCallbackHandler(tracer)
    root_id = uuid4()
    retrieval_id = uuid4()
    callback.on_chain_start({"name": "qa"}, {}, run_id=root_id)
    callback.on_chain_start({"name": "qa"}, {}, run_id=root_id)
    callback.on_retriever_start({"name": "retriever"}, "question", run_id=retrieval_id, parent_run_id=root_id)
    callback.on_retriever_end([], run_id=retrieval_id, parent_run_id=root_id)
    callback.on_retriever_end([], run_id=retrieval_id, parent_run_id=root_id)
    callback.on_chain_end({}, run_id=root_id)
    callback.on_chain_end({}, run_id=root_id)

    assert len(tracer.runs) == 1
    run = tracer.runs[0]
    assert len([e for e in run.events if e.event_type == "retrieval"]) == 1
    assert len(run.exit_calls) == 1


def test_callback_error_closes_root_run_and_preserves_error_status():
    tracer = FakeTracer()
    callback = integration_module.TraceLensCallbackHandler(tracer)
    root_id = uuid4()
    error = RuntimeError("generation failed")
    callback.on_chain_start({"name": "qa"}, {}, run_id=root_id)
    callback.on_chain_error(error, run_id=root_id)
    run = tracer.runs[0]
    assert run.exit_calls[0][0] is RuntimeError
    assert any(event.status == "failed" for event in run.events)
