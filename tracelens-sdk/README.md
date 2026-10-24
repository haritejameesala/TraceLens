# TraceLens SDK

Install from this directory with `pip install -e .`. Use `TraceLens(project_id, api_url=..., strict=True)` after creating a project through the backend. `strict=True` surfaces delivery failures; use `strict=False` only when application continuity is preferred, and inspect delivery outcomes/logging in your application. The SDK sends HTTP events to FastAPI; it does not connect directly to MongoDB.

Only include safe, explicit metadata in event payloads. Do not include credentials, tokens, or full sensitive request bodies.
