"""Developer diagnostics and startup-capture commands for TraceLens."""
from __future__ import annotations

import argparse
import importlib.util
import os
import runpy
import sys
from pathlib import Path

import httpx

from . import __version__
from .client import TraceLens


def _load_dotenv_if_available() -> None:
    """Load a local .env when python-dotenv is installed; never override shell env."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(override=False)


def main() -> int:
    """Check SDK configuration and backend health (tracelens-doctor)."""
    _load_dotenv_if_available()
    api_url = os.getenv("TRACELENS_API_URL", "http://127.0.0.1:8000").rstrip("/")
    project_id = os.getenv("TRACELENS_PROJECT_ID", "").strip()
    print(f"TraceLens SDK: {__version__}")
    print(f"API URL: {api_url}")
    print(f"Project ID configured: {'yes' if project_id else 'no'}")
    print(f"LangChain integration installed: {'yes' if importlib.util.find_spec('langchain_core') else 'no'}")
    try:
        response = httpx.get(f"{api_url}/health", timeout=3.0)
        response.raise_for_status()
        print(f"Backend health: OK (HTTP {response.status_code})")
    except Exception as exc:
        print(f"Backend health: FAILED ({type(exc).__name__})")
        return 1
    if not project_id:
        print("Set TRACELENS_PROJECT_ID to an existing TraceLens project ID before tracing runs.")
        return 2
    print("Configuration checks passed. This check does not validate project permissions or event ingestion.")
    return 0


def run_main() -> int:
    """Execute a Python script inside a TraceLens run, including parse-time failures.

    Use ``python -m tracelens_sdk.cli path/to/script.py`` when the console-script
    executable is unavailable or blocked by host application-control policy.
    The target exception is re-raised after TraceRun attempts to persist failure
    telemetry, preserving normal Python failure behavior.
    """
    _load_dotenv_if_available()
    parser = argparse.ArgumentParser(
        prog="tracelens-run",
        description="Run a Python script with TraceLens startup-failure capture",
    )
    parser.add_argument("--run-name", default=None, help="Optional TraceLens run scenario name")
    parser.add_argument("script", help="Path to the Python script to execute")
    parser.add_argument("script_args", nargs=argparse.REMAINDER, help="Arguments passed to the target script")
    args = parser.parse_args()

    project_id = os.getenv("TRACELENS_PROJECT_ID", "").strip()
    if not project_id:
        print("Set TRACELENS_PROJECT_ID to an existing TraceLens project ID (or put it in .env).", file=sys.stderr)
        return 2

    script_path = Path(args.script).expanduser().resolve()
    if not script_path.is_file():
        print(f"Script not found: {script_path}", file=sys.stderr)
        return 2
    if script_path.suffix.lower() != ".py":
        print(f"Expected a Python .py script: {script_path}", file=sys.stderr)
        return 2

    previous_argv = sys.argv[:]
    previous_path = sys.path[:]
    sys.argv = [str(script_path), *args.script_args]
    # Match ``python path/to/script.py`` import behavior for sibling modules.
    sys.path.insert(0, str(script_path.parent))
    tracer = None
    try:
        tracer = TraceLens(
            project_id,
            api_url=os.getenv("TRACELENS_API_URL", "http://127.0.0.1:8000"),
            strict=False,
        )
        with tracer.start_run(
            args.run_name or f"startup:{script_path.name}",
            metadata={"capture_mode": "script_wrapper", "script_path": str(script_path)},
        ):
            runpy.run_path(str(script_path), run_name="__main__")
        return 0
    finally:
        sys.argv = previous_argv
        sys.path[:] = previous_path
        if tracer is not None:
            tracer.close()


if __name__ == "__main__":
    # Keep ``python -m tracelens_sdk.cli`` as the doctor command, while an
    # additional script argument invokes the startup-capture launcher.
    sys.exit(run_main() if len(sys.argv) > 1 else main())
