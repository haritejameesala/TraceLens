from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from fastapi import FastAPI, HTTPException
from pymongo.errors import DuplicateKeyError
from app.db import client, db, ensure_indexes
from app.models import ProjectCreate, RunCreate, RunUpdate, EventCreate, CompareRequest, make_id
from app.diagnostics import diagnose

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tracelens")


def clean(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup does not claim readiness until MongoDB ping and indexes succeed.
    await client.admin.command("ping")
    await ensure_indexes()
    logger.info("TraceLens backend ready; MongoDB connected; database=%s", db.name)
    try:
        yield
    finally:
        client.close()


app = FastAPI(title="TraceLens API", version="0.4.0", lifespan=lifespan)


@app.get("/health")
async def health():
    try:
        await client.admin.command("ping")
        return {"status": "ok", "database": "connected", "database_name": db.name}
    except Exception as exc:
        logger.warning("Database readiness check failed: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail={"status": "unavailable", "database": "disconnected", "error_type": type(exc).__name__})


@app.post("/api/projects", status_code=201)
async def create_project(body: ProjectCreate):
    doc = {"project_id": make_id("prj"), **body.model_dump(), "created_at": datetime.now(timezone.utc)}
    await db.projects.insert_one(doc)
    return clean(doc)


@app.get("/api/projects")
async def list_projects():
    return [clean(x) async for x in db.projects.find().sort("created_at", -1).limit(200)]


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
