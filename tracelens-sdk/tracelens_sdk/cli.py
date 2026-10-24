"""Developer diagnostics command for TraceLens SDK installations."""
from __future__ import annotations
import os
import sys
import importlib.util
import httpx
from . import __version__

def main() -> int:
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
        print("Set TRACELENS_PROJECT_ID to an existing project ID before tracing runs.")
        return 2
    print("Configuration checks passed. This check does not validate project permissions or event ingestion.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
