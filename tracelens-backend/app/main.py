from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pymongo.errors import DuplicateKeyError
from app.db import client, db, ensure_indexes
from app.models import ProjectCreate, RunCreate, RunUpdate, EventCreate, CompareRequest, make_id
from app.diagnostics import diagnose
def clean(doc):
    if doc is None: return None
    doc = dict(doc); doc.pop("_id", None); return doc
@asynccontextmanager
async def lifespan(app):
    await ensure_indexes()
    yield
    client.close()
app = FastAPI(title="TraceLens API", version="0.3.0", lifespan=lifespan)
@app.get("/health")
async def health():
    try:
        await client.admin.command("ping")
        return {"status":"ok","database":"connected"}
    except Exception:
        raise HTTPException(503,"MongoDB unavailable")
@app.post("/api/projects", status_code=201)
async def create_project(body: ProjectCreate):
    doc={"project_id":make_id("prj"),**body.model_dump(),"created_at":datetime.now(timezone.utc)}
    await db.projects.insert_one(doc); return clean(doc)
@app.get("/api/projects")
async def list_projects():
    return [clean(x) async for x in db.projects.find().sort("created_at",-1).limit(200)]
@app.post("/api/runs", status_code=201)
async def create_run(body: RunCreate):
    if not await db.projects.find_one({"project_id":body.project_id}): raise HTTPException(404,"Project not found")
    now=datetime.now(timezone.utc)
    doc={"run_id":make_id("run"),**body.model_dump(),"created_at":now,"updated_at":now}
    await db.runs.insert_one(doc); return clean(doc)
@app.patch("/api/runs/{run_id}")
async def update_run(run_id: str, body: RunUpdate):
    result=await db.runs.update_one({"run_id":run_id},{"$set":{"status":body.status,"updated_at":datetime.now(timezone.utc)}})
    if not result.matched_count: raise HTTPException(404,"Run not found")
    return {"run_id":run_id,"status":body.status}
@app.get("/api/projects/{project_id}/runs")
async def list_runs(project_id: str):
    return [clean(x) async for x in db.runs.find({"project_id":project_id}).sort("created_at",-1).limit(200)]
@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    x=await db.runs.find_one({"run_id":run_id})
    if not x: raise HTTPException(404,"Run not found")
    return clean(x)
@app.post("/api/runs/{run_id}/events", status_code=201)
async def create_event(run_id: str, body: EventCreate):
    if not await db.runs.find_one({"run_id":run_id}): raise HTTPException(404,"Run not found")
    try: await db.events.insert_one({"run_id":run_id,**body.model_dump()})
    except DuplicateKeyError: return {"status":"duplicate_ignored","event_id":body.event_id}
    await db.runs.update_one({"run_id":run_id},{"$set":{"updated_at":datetime.now(timezone.utc)}})
    return {"status":"stored","event_id":body.event_id}
@app.get("/api/runs/{run_id}/events")
async def list_events(run_id: str):
    if not await db.runs.find_one({"run_id":run_id}): raise HTTPException(404,"Run not found")
    return [clean(x) async for x in db.events.find({"run_id":run_id}).sort("timestamp",1)]
@app.post("/api/runs/compare")
async def compare_runs(body: CompareRequest):
    base=await db.runs.find_one({"run_id":body.baseline_run_id})
    curr=await db.runs.find_one({"run_id":body.current_run_id})
    if not base or not curr: raise HTTPException(404,"Run not found")
    if base["project_id"] != curr["project_id"]: raise HTTPException(400,"Runs must belong to same project")
    be=[clean(x) async for x in db.events.find({"run_id":body.baseline_run_id}).sort("timestamp",1)]
    ce=[clean(x) async for x in db.events.find({"run_id":body.current_run_id}).sort("timestamp",1)]
    findings=[]
    for f in diagnose(be,ce):
        doc={"finding_id":make_id("fnd"),"run_id":body.current_run_id,"baseline_run_id":body.baseline_run_id,
             **f,"created_at":datetime.now(timezone.utc)}
        await db.findings.insert_one(doc); findings.append(clean(doc))
    return {"baseline":{"run_id":base["run_id"],"scenario":base["scenario"],"status":base["status"]},
            "current":{"run_id":curr["run_id"],"scenario":curr["scenario"],"status":curr["status"]},
            "event_counts":{"baseline":len(be),"current":len(ce)},"findings":findings}
@app.get("/api/runs/{run_id}/findings")
async def list_findings(run_id: str):
    return [clean(x) async for x in db.findings.find({"run_id":run_id}).sort("created_at",-1).limit(100)]
