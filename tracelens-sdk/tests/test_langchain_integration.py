"""Callback contract tests; CI installs the optional LangChain dependency."""
from uuid import uuid4
import pytest

pytest.importorskip("langchain_core.callbacks")
from tracelens_sdk import langchain_callback


class FakeRun:
    def __init__(self):
        self.events = []
        self.entered = False
        self.exit_args = None
        self.trace_id = "fake-trace-id"

    def __enter__(self):
        self.entered = True
        return self

    def record_event(self, event):
        self.events.append(event)

    def __exit__(self, *args):
        self.exit_args = args


class FakeTracer:
    def __init__(self):
        self.runs = []

    def start_run(self, *args, **kwargs):
        run = FakeRun()
        self.runs.append(run)
        return run


def test_callback_records_root_retrieval_and_finishes_run():
    tracer = FakeTracer()
    callback = langchain_callback(tracer, run_name="test-rag")
    root = uuid4()
    retriever = uuid4()
    callback.on_chain_start({"name": "qa-chain"}, {"question": "secret question"}, run_id=root)
    callback.on_retriever_start({"name": "test-retriever"}, "question", run_id=retriever, parent_run_id=root)
    callback.on_retriever_end([], run_id=retriever, parent_run_id=root)
    callback.on_chain_end({"answer": "secret answer"}, run_id=root)

    assert len(tracer.runs) == 1
    run = tracer.runs[0]
    assert run.entered and run.exit_args == (None, None, None)
    assert all(event.trace_id == run.trace_id for event in run.events)
    retrieval = [event for event in run.events if event.event_type == "retrieval"]
    assert len(retrieval) == 1
    assert retrieval[0].payload["retrieved_chunk_count"] == 0
    assert "secret question" not in repr([event.payload for event in run.events])
    assert "secret answer" not in repr([event.payload for event in run.events])


def test_callback_records_chain_error_and_closes_root_run():
    tracer = FakeTracer()
    callback = langchain_callback(tracer)
    root = uuid4()
    error = RuntimeError("expected test error")
    callback.on_chain_start({"name": "qa-chain"}, {}, run_id=root)
    callback.on_chain_error(error, run_id=root)
    assert tracer.runs[0].exit_args[0] is RuntimeError
    assert any(event.status == "failed" for event in tracer.runs[0].events)
