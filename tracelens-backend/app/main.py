from contextlib import asynccontextmanager
from datetime import datetime, timezone
import re
import logging
import json
import secrets
import httpx
from fastapi import FastAPI, HTTPException, Response, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import DuplicateKeyError
from app.db import client, db, ensure_indexes, deduplicate_legacy_projects
from app.models import ProjectCreate, ProjectUpdate, RunCreate, RunUpdate, RunDetailsUpdate, EventCreate, CompareRequest, make_id
from app.diagnostics import diagnose
from app.investigation import deterministic_diagnosis, enrich_with_ollama, normalize_evidence_event_ids
from app.config import settings
from app.memory import error_signature, redact
from app.serialization import clean

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tracelens")



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup does not claim readiness until MongoDB ping and indexes succeed.
    await client.admin.command("ping")
    await deduplicate_legacy_projects()
    await ensure_indexes()
    await db.projects.create_index("project_key", unique=True, sparse=True)
    logger.info("TraceLens backend ready; MongoDB connected; database=%s", db.name)
    try:
        yield
    finally:
        client.close()


app = FastAPI(title="TraceLens API", version="0.5.6", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-TraceLens-API-Key"],
)


def _sdk_key_map() -> dict[str, str]:
    """Parse project-scoped SDK secrets from backend environment without logging secrets."""
    raw = settings.tracelens_sdk_keys.strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("TRACELENS_SDK_KEYS must be a JSON object mapping project IDs to secrets") from exc
    if not isinstance(value, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in value.items()):
        raise RuntimeError("TRACELENS_SDK_KEYS must be a JSON object mapping project IDs to string secrets")
    return {k: v for k, v in value.items() if k and v}


@app.middleware("http")
async def authenticate_sdk_ingestion(request: Request, call_next):
    """Authenticate SDK writes when project-scoped keys are configured.

    Dashboard reads and local development remain unchanged. SDK ingestion routes are
    protected once TRACELENS_SDK_KEYS is configured.
    """
    protected = (
        request.method == "POST" and request.url.path in {"/api/runs",}
    ) or (
        request.method == "POST" and re.fullmatch(r"/api/runs/[^/]+/events", request.url.path)
    ) or (
        request.method == "PATCH" and re.fullmatch(r"/api/runs/[^/]+", request.url.path)
    )
    if not protected:
        return await call_next(request)
    keys = _sdk_key_map()
    if not keys:
        return await call_next(request)
    supplied = request.headers.get("X-TraceLens-API-Key", "").strip()
    project_id = None
    if request.url.path == "/api/runs" and request.method == "POST":
        try:
            body = await request.json()
            project_id = body.get("project_id") if isinstance(body, dict) else None
        except Exception:
            project_id = None
    else:
        run_id = request.url.path.split("/")[3]
        run = await db.runs.find_one({"run_id": run_id}, {"project_id": 1})
        project_id = run.get("project_id") if run else None
    expected = keys.get(str(project_id)) if project_id else None
    if not expected or not supplied or not secrets.compare_digest(supplied, expected):
        from starlette.responses import JSONResponse
        return JSONResponse({"detail": "Invalid or missing TraceLens SDK key for this project"}, status_code=401)
    return await call_next(request)


@app.get("/health")
async def health():
    try:
        await client.admin.command("ping")
        return {"status": "ok", "database": "connected", "database_name": db.name}
    except Exception as exc:
        logger.warning("Database readiness check failed: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail={"status": "unavailable", "database": "disconnected", "error_type": type(exc).__name__})


@app.post("/api/projects", status_code=201)
async def create_project(body: ProjectCreate, response: Response):
    # Idempotency is explicit when project_key is supplied. For older SDK/demo clients,
    # reuse a same-name + same-framework project rather than creating duplicates.
    values = body.model_dump()
    key = values.get("project_key")
    if not key:
        key = re.sub(r"[^a-z0-9]+", "-", f"{body.name}-{body.framework}".lower()).strip("-")[:150]
        values["project_key"] = key
    existing = await db.projects.find_one({"project_key": key})
    if existing:
        response.status_code = 200
        # Keep the existing identity and history; update descriptive fields only.
        await db.projects.update_one({"project_id": existing["project_id"]}, {"$set": {
            "name": body.name, "description": body.description, "framework": body.framework
        }})
        existing.update({"name": body.name, "description": body.description, "framework": body.framework})
        return clean(existing)
    # Legacy duplicate protection for records created before project_key existed.
    existing = await db.projects.find_one({"name": body.name, "framework": body.framework})
    if existing:
        response.status_code = 200
        await db.projects.update_one({"project_id": existing["project_id"]}, {"$set": {"project_key": key}})
        existing["project_key"] = key
        return clean(existing)
    doc = {"project_id": make_id("prj"), **values, "created_at": datetime.now(timezone.utc)}
    try:
        await db.projects.insert_one(doc)
    except DuplicateKeyError:
        existing = await db.projects.find_one({"project_key": key})
        if existing:
            return clean(existing)
        raise
    return clean(doc)


@app.get("/api/projects")
async def list_projects():
    return [clean(x) async for x in db.projects.find().sort("created_at", -1).limit(200)]


@app.patch("/api/projects/{project_id}")
async def update_project(project_id: str, body: ProjectUpdate):
    """Rename a project or update its descriptive metadata without changing its stable identity."""
    values = body.model_dump()
    result = await db.projects.update_one({"project_id": project_id}, {"$set": values})
    if not result.matched_count:
        raise HTTPException(404, "Project not found")
    updated = await db.projects.find_one({"project_id": project_id})
    return clean(updated)


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project and all of its dependent run, event, finding and investigation records."""
    project = await db.projects.find_one({"project_id": project_id})
    if not project:
        raise HTTPException(404, "Project not found")
    run_ids = [item["run_id"] async for item in db.runs.find({"project_id": project_id}, {"run_id": 1})]
    if run_ids:
        await db.events.delete_many({"run_id": {"$in": run_ids}})
        await db.findings.delete_many({"$or": [
            {"run_id": {"$in": run_ids}},
            {"baseline_run_id": {"$in": run_ids}},
        ]})
        await db.investigations.delete_many({"$or": [
            {"project_id": project_id},
            {"run_id": {"$in": run_ids}},
        ]})
        await db.runs.delete_many({"project_id": project_id})
    await db.incident_memories.delete_many({"project_id": project_id})
    await db.projects.delete_one({"project_id": project_id})
    return {"status": "deleted", "project_id": project_id, "deleted_runs": len(run_ids)}


@app.post("/api/runs", status_code=201)
async def create_run(body: RunCreate):
    if not await db.projects.find_one({"project_id": body.project_id}):
        raise HTTPException(404, "Project not found")
    if body.baseline_run_id:
        baseline = await db.runs.find_one({"run_id": body.baseline_run_id})
        if not baseline or baseline["project_id"] != body.project_id:
            raise HTTPException(400, "Baseline run must exist and belong to the same project")
    now = datetime.now(timezone.utc)
    doc = {"run_id": make_id("run"), **body.model_dump(), "created_at": now, "updated_at": now}
    await db.runs.insert_one(doc)
    return clean(doc)


@app.patch("/api/runs/{run_id}")
async def update_run(run_id: str, body: RunUpdate):
    result = await db.runs.update_one({"run_id": run_id}, {"$set": {"status": body.status, "updated_at": datetime.now(timezone.utc)}})
    if not result.matched_count:
        raise HTTPException(404, "Run not found")
    return {"run_id": run_id, "status": body.status}


@app.get("/api/projects/{project_id}/runs")
async def list_runs(project_id: str):
    return [clean(x) async for x in db.runs.find({"project_id": project_id}).sort("created_at", -1).limit(200)]


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    doc = await db.runs.find_one({"run_id": run_id})
    if not doc:
        raise HTTPException(404, "Run not found")
    return clean(doc)


@app.patch("/api/runs/{run_id}/details")
async def update_run_details(run_id: str, body: RunDetailsUpdate):
    """Rename a run's display scenario without changing run identity or stored events."""
    result = await db.runs.update_one({"run_id": run_id}, {"$set": {"scenario": body.scenario, "updated_at": datetime.now(timezone.utc)}})
    if not result.matched_count:
        raise HTTPException(404, "Run not found")
    return {"run_id": run_id, "scenario": body.scenario}


@app.delete("/api/runs/{run_id}")
async def delete_run(run_id: str):
    """Delete a run and its dependent records without deleting the project."""
    run = await db.runs.find_one({"run_id": run_id})
    if not run:
        raise HTTPException(404, "Run not found")
    await db.events.delete_many({"run_id": run_id})
    await db.findings.delete_many({"$or": [
        {"run_id": run_id},
        {"baseline_run_id": run_id},
    ]})
    await db.investigations.delete_many({"run_id": run_id})
    await db.incident_memories.update_many({"run_id": run_id}, {"$set": {"source_run_deleted": True}})
    await db.runs.delete_one({"run_id": run_id})
    # Remove baseline references to the deleted run from remaining runs.
    await db.runs.update_many({"baseline_run_id": run_id}, {"$set": {"baseline_run_id": None}})
    return {"status": "deleted", "run_id": run_id}


@app.post("/api/runs/{run_id}/events", status_code=201)
async def create_event(run_id: str, body: EventCreate):
    if not await db.runs.find_one({"run_id": run_id}):
        raise HTTPException(404, "Run not found")
    try:
        await db.events.insert_one({"run_id": run_id, **body.model_dump()})
    except DuplicateKeyError:
        return {"status": "duplicate_ignored", "event_id": body.event_id}
    await db.runs.update_one({"run_id": run_id}, {"$set": {"updated_at": datetime.now(timezone.utc)}})
    return {"status": "stored", "event_id": body.event_id}


@app.get("/api/runs/{run_id}/events")
async def list_events(run_id: str):
    if not await db.runs.find_one({"run_id": run_id}):
        raise HTTPException(404, "Run not found")
    return [clean(x) async for x in db.events.find({"run_id": run_id}).sort("timestamp", 1)]


@app.post("/api/runs/compare")
async def compare_runs(body: CompareRequest):
    base = await db.runs.find_one({"run_id": body.baseline_run_id})
    curr = await db.runs.find_one({"run_id": body.current_run_id})
    if not base or not curr:
        raise HTTPException(404, "Run not found")
    if base["project_id"] != curr["project_id"]:
        raise HTTPException(400, "Runs must belong to same project")
    base_events = [clean(x) async for x in db.events.find({"run_id": body.baseline_run_id}).sort("timestamp", 1)]
    current_events = [clean(x) async for x in db.events.find({"run_id": body.current_run_id}).sort("timestamp", 1)]
    findings = []
    for rule in diagnose(base_events, current_events):
        evidence_ids = rule.get("evidence_event_ids", [])
        valid_ids = {e["event_id"] for e in base_events + current_events}
        if any(event_id not in valid_ids for event_id in evidence_ids):
            logger.error("Diagnostic rule returned a non-existent evidence ID")
            raise HTTPException(500, "Diagnostic generated invalid evidence references")
        doc = {"finding_id": make_id("fnd"), "run_id": body.current_run_id,
               "baseline_run_id": body.baseline_run_id, **rule,
               "created_at": datetime.now(timezone.utc)}
        await db.findings.insert_one(doc)
        findings.append(clean(doc))
    return {"baseline": {"run_id": base["run_id"], "scenario": base["scenario"], "status": base["status"]},
            "current": {"run_id": curr["run_id"], "scenario": curr["scenario"], "status": curr["status"]},
            "event_counts": {"baseline": len(base_events), "current": len(current_events)}, "findings": findings}


@app.get("/api/runs/{run_id}/findings")
async def list_findings(run_id: str):
    if not await db.runs.find_one({"run_id": run_id}):
        raise HTTPException(404, "Run not found")
    return [clean(x) async for x in db.findings.find({"run_id": run_id}).sort("created_at", -1).limit(100)]


@app.post("/api/runs/{run_id}/investigate")
async def investigate_run(run_id: str):
    """Investigate one run using its full timeline and same-project run history."""
    run = await db.runs.find_one({"run_id": run_id})
    if not run:
        raise HTTPException(404, "Run not found")
    events = [clean(x) async for x in db.events.find({"run_id": run_id}).sort("timestamp", 1)]
    history = [clean(x) async for x in db.runs.find({"project_id": run["project_id"]}).sort("created_at", -1).limit(60)]
    # Prefer successful comparable runs as baselines; include similar failed runs for recurrence.
    other_runs = [r for r in history if r.get("run_id") != run_id]
    successful_baselines = [r for r in other_runs if str(r.get("status", "")).lower() in {"success", "succeeded", "completed"}]
    same_version_scenario = [r for r in successful_baselines if (not run.get("version") or not r.get("version") or run.get("version") == r.get("version")) and (not run.get("scenario") or not r.get("scenario") or run.get("scenario") == r.get("scenario"))]
    prioritized = same_version_scenario + [r for r in successful_baselines if r not in same_version_scenario] + [r for r in other_runs if r not in successful_baselines]
    # Preserve order while deduplicating and keep a bounded set of most useful comparison runs.
    prior_runs = []
    seen_run_ids = set()
    for item in prioritized:
        rid = item.get("run_id")
        if rid and rid not in seen_run_ids:
            seen_run_ids.add(rid)
            prior_runs.append(item)
        if len(prior_runs) >= 12:
            break
    prior_ids = [r["run_id"] for r in prior_runs]
    historical_events = []
    # Query each run separately so one verbose recent trace cannot crowd out every baseline.
    for prior_id in prior_ids:
        per_run_events = [clean(x) async for x in db.events.find({"run_id": prior_id}).sort("timestamp", 1).limit(40)]
        historical_events.extend(per_run_events)
    report = deterministic_diagnosis(clean(run), events, history, historical_events)
    provider_status = "deterministic"
    if settings.rca_provider.lower() == "ollama":
        try:
            report = await enrich_with_ollama(report, clean(run), events, history, historical_events, settings.rca_ollama_base_url, settings.rca_ollama_model, settings.rca_timeout_seconds)
            provider_status = "ollama"
        except Exception as exc:
            # RCA remains available without the LLM; expose the specific failure category
            # without returning raw exception strings that could contain sensitive details.
            from urllib.parse import urlsplit
            report["ai_status"] = "unavailable"
            report["ai_error_type"] = type(exc).__name__
            parsed = urlsplit(settings.rca_ollama_base_url)
            endpoint = f"{parsed.hostname}:{parsed.port or (443 if parsed.scheme == 'https' else 80)}" if parsed.hostname else "configured Ollama endpoint"
            if isinstance(exc, httpx.ConnectError):
                report["ai_fallback_reason"] = f"Could not connect to the RCA model service at {endpoint}; deterministic diagnosis was retained. Check RCA_OLLAMA_BASE_URL and service availability."
            elif isinstance(exc, httpx.TimeoutException):
                report["ai_fallback_reason"] = f"The RCA model service at {endpoint} timed out; deterministic diagnosis was retained. Check model load and RCA_TIMEOUT_SECONDS."
            elif isinstance(exc, (ValueError, KeyError)):
                report["ai_fallback_reason"] = "The RCA model returned an invalid or unexpected response; deterministic diagnosis was retained."
            elif isinstance(exc, httpx.HTTPStatusError):
                report["ai_fallback_reason"] = f"The RCA model service returned HTTP {exc.response.status_code}; deterministic diagnosis was retained. Check model name and server response."
            else:
                report["ai_fallback_reason"] = f"RCA enrichment failed ({type(exc).__name__}); deterministic diagnosis was retained."
            logger.warning("RCA model unavailable for run %s: %s", run_id, type(exc).__name__)
    else:
        report["ai_status"] = "disabled"
    valid_event_ids = {e.get("event_id") for e in events if e.get("event_id")}
    report["evidence_event_ids"] = normalize_evidence_event_ids(report.get("evidence_event_ids", []), valid_event_ids)
    if not report["evidence_event_ids"]:
        fallback_evidence = [e.get("event_id") for e in events if e.get("event_id") and (e.get("status") == "failed" or e.get("error") or e.get("event_type") == "error")]
        report["evidence_event_ids"] = list(dict.fromkeys(fallback_evidence[:3]))
    # The stored trace is the timeline source of truth. Preserve model explanations
    # only as annotations; never let an empty/malformed model response blank the UI.
    model_timeline = report.get("timeline") if isinstance(report.get("timeline"), list) else []
    explanations = {item.get("event_id"): str(item.get("explanation"))[:1000]
                    for item in model_timeline if isinstance(item, dict)
                    and item.get("event_id") in valid_event_ids and item.get("explanation")}
    report["timeline"] = []
    for event in sorted(events, key=lambda item: str(item.get("timestamp", ""))):
        timestamp = event.get("timestamp", "")
        if isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat()
        item = {"event_id": event.get("event_id"), "timestamp": str(timestamp),
                "step": event.get("step"), "status": event.get("status"), "event_type": event.get("event_type"),
                "duration_ms": event.get("duration_ms"), "error": event.get("error") or ""}
        if item["event_id"] in explanations:
            item["explanation"] = explanations[item["event_id"]]
        report["timeline"].append(item)
    now = datetime.now(timezone.utc)
    report_doc = {"investigation_id": make_id("inv"), "run_id": run_id, "project_id": run["project_id"], "created_at": now, **report}
    await db.investigations.insert_one(report_doc)
    # Automatically create a project-scoped incident memory from a failed or suspicious run.
    # Store a redacted summary and event references, not raw payloads or prompts.
    signature = error_signature(clean(run), events, report)
    if str(run.get("status", "")).lower() == "failed" or any(e.get("status") == "failed" or e.get("error") for e in events):
        memory_doc = {
            "memory_id": make_id("mem"), "project_id": run["project_id"], "run_id": run_id,
            "investigation_id": report_doc["investigation_id"], **signature,
            "evidence_event_ids": report.get("evidence_event_ids", [])[:10],
            "outcome": "unverified", "verified_fix": None, "created_at": now,
            "source": "automatic_investigation",
        }
        await db.incident_memories.update_one(
            {"project_id": run["project_id"], "run_id": run_id, "signature": signature["signature"]},
            {"$setOnInsert": memory_doc}, upsert=True,
        )
    return clean(report_doc)


@app.get("/api/projects/{project_id}/memories")
async def list_project_memories(project_id: str):
    if not await db.projects.find_one({"project_id": project_id}):
        raise HTTPException(404, "Project not found")
    return [clean(x) async for x in db.incident_memories.find({"project_id": project_id}).sort("created_at", -1).limit(200)]


@app.post("/api/memories/{memory_id}/confirm-fix")
async def confirm_memory_fix(memory_id: str, body: dict = Body(...)):
    """Promote a proposed fix only after explicit user confirmation with a concise outcome note."""
    note = redact(str(body.get("fix", "")).strip(), 1000)
    if not note:
        raise HTTPException(422, "fix must describe the confirmed corrective action")
    result = await db.incident_memories.update_one({"memory_id": memory_id}, {"$set": {
        "outcome": "user_verified", "verified_fix": note,
        "verified_at": datetime.now(timezone.utc), "verification_source": "explicit_user_confirmation",
    }})
    if not result.matched_count:
        raise HTTPException(404, "Incident memory not found")
    return clean(await db.incident_memories.find_one({"memory_id": memory_id}))


@app.get("/api/runs/{run_id}/investigations")
async def list_investigations(run_id: str):
    if not await db.runs.find_one({"run_id": run_id}):
        raise HTTPException(404, "Run not found")
    return [clean(x) async for x in db.investigations.find({"run_id": run_id}).sort("created_at", -1).limit(20)]
