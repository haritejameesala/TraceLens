import sys
import pytest
from tracelens_sdk import cli


class FakeRun:
    def __init__(self, recorder):
        self.recorder = recorder
    def __enter__(self):
        self.recorder["entered"] = True
        return self
    def __exit__(self, exc_type, exc, tb):
        self.recorder["exception_type"] = exc_type.__name__ if exc_type else None
        return False


class FakeTracer:
    def __init__(self, *args, **kwargs):
        self.recorder = {"init": kwargs, "closed": False}
        TRACERS.append(self)
    def start_run(self, name, **kwargs):
        self.recorder["run_name"] = name
        self.recorder["metadata"] = kwargs.get("metadata")
        return FakeRun(self.recorder)
    def close(self):
        self.recorder["closed"] = True


TRACERS = []


def test_script_wrapper_records_syntax_error_before_app_instrumentation(tmp_path, monkeypatch):
    script = tmp_path / "broken.py"
    script.write_text("def broken(:\n    pass\n", encoding="utf-8")
    monkeypatch.setenv("TRACELENS_PROJECT_ID", "project-test")
    monkeypatch.setattr(cli, "TraceLens", FakeTracer)
    monkeypatch.setattr(sys, "argv", ["tracelens-run", str(script), "--", "arg1"])
    TRACERS.clear()
    with pytest.raises(SyntaxError):
        cli.run_main()
    assert TRACERS[0].recorder["exception_type"] == "SyntaxError"
    assert TRACERS[0].recorder["closed"] is True
    assert TRACERS[0].recorder["metadata"]["capture_mode"] == "script_wrapper"


def test_script_wrapper_requires_project_id(tmp_path, monkeypatch):
    script = tmp_path / "ok.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.delenv("TRACELENS_PROJECT_ID", raising=False)
    monkeypatch.setattr(sys, "argv", ["tracelens-run", str(script)])
    assert cli.run_main() == 2


def test_script_wrapper_reports_missing_script(monkeypatch):
    monkeypatch.setenv("TRACELENS_PROJECT_ID", "project-test")
    monkeypatch.setattr(sys, "argv", ["tracelens-run", "/does/not/exist.py"])
    assert cli.run_main() == 2


def test_script_wrapper_records_import_error_before_sdk_initialization(tmp_path, monkeypatch):
    script = tmp_path / "missing_import.py"
    script.write_text("import tracelens_this_package_does_not_exist\n", encoding="utf-8")
    monkeypatch.setenv("TRACELENS_PROJECT_ID", "project-test")
    monkeypatch.setattr(cli, "TraceLens", FakeTracer)
    monkeypatch.setattr(sys, "argv", ["tracelens-run", str(script)])
    TRACERS.clear()
    with pytest.raises(ModuleNotFoundError):
        cli.run_main()
    assert TRACERS[0].recorder["exception_type"] == "ModuleNotFoundError"
    assert TRACERS[0].recorder["closed"] is True


def test_script_wrapper_executes_script_and_restores_process_state(tmp_path, monkeypatch):
    script = tmp_path / "ok.py"
    script.write_text("import sys\nassert sys.argv[1:] == ['hello']\n", encoding="utf-8")
    monkeypatch.setenv("TRACELENS_PROJECT_ID", "project-test")
    monkeypatch.setattr(cli, "TraceLens", FakeTracer)
    original_path = sys.path[:]
    monkeypatch.setattr(sys, "argv", ["tracelens-run", str(script), "hello"])
    TRACERS.clear()

    assert cli.run_main() == 0
    assert TRACERS[0].recorder["exception_type"] is None
    assert TRACERS[0].recorder["closed"] is True
    assert sys.path == original_path
