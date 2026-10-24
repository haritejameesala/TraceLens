import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

client_options = {
    "serverSelectionTimeoutMS": settings.mongo_server_selection_timeout_ms,
    "connectTimeoutMS": 10000,
    "retryWrites": True,
}
# PyMongo/Motor verifies TLS certificates by default. Use certifi's CA bundle for
# predictable cross-platform trust; never disable certificate verification.
if settings.mongodb_uri.startswith("mongodb+srv://") or settings.mongodb_uri.startswith("mongodb://"):
    client_options["tlsCAFile"] = settings.mongodb_tls_ca_file or certifi.where()

client = AsyncIOMotorClient(settings.mongodb_uri, **client_options)
db = client[settings.mongodb_database]


async def ensure_indexes():
    await db.projects.create_index("project_id", unique=True)
    await db.runs.create_index("run_id", unique=True)
    await db.runs.create_index([("project_id", 1), ("created_at", -1)])
    await db.events.create_index("event_id", unique=True)
    await db.events.create_index([("run_id", 1), ("timestamp", 1)])
    await db.findings.create_index("finding_id", unique=True)
    await db.findings.create_index([("run_id", 1), ("created_at", -1)])
