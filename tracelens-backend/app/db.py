from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=4000)
db = client[settings.mongodb_database]
async def ensure_indexes():
    await db.projects.create_index("project_id", unique=True)
    await db.runs.create_index("run_id", unique=True)
    await db.runs.create_index([("project_id", 1), ("created_at", -1)])
    await db.events.create_index("event_id", unique=True)
    await db.events.create_index([("run_id", 1), ("timestamp", 1)])
    await db.findings.create_index("finding_id", unique=True)
    await db.findings.create_index([("run_id", 1), ("severity", 1)])
