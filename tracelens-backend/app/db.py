import certifi
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

client_options = {
    "serverSelectionTimeoutMS": settings.mongo_server_selection_timeout_ms,
    "connectTimeoutMS": 10000,
    "retryWrites": True,
}
# PyMongo/Motor verifies TLS certificates by default. Use certifi's CA bundle for
# predictable cross-platform trust; never disable certificate verification.
if settings.mongodb_uri.startswith("mongodb+srv://"):
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
    await db.investigations.create_index("investigation_id", unique=True)
    await db.investigations.create_index([("run_id", 1), ("created_at", -1)])
    # Create this only after legacy records have been consolidated at startup.


async def deduplicate_legacy_projects():
    """Merge exact duplicate projects before the unique project_key index is created.

    Canonical project = oldest record for the same exact name + framework. Reassign
    runs without changing run IDs; events and findings therefore retain their links.
    """
    import re
    pipeline = [
        {"$group": {
            "_id": {"name": "$name", "framework": "$framework"},
            "docs": {"$push": {"project_id": "$project_id", "created_at": "$created_at", "project_key": "$project_key"}},
            "count": {"$sum": 1},
        }},
        {"$match": {"count": {"$gt": 1}}},
    ]
    async for group in db.projects.aggregate(pipeline):
        docs = sorted(
            group["docs"],
            key=lambda d: (
                d.get("created_at") or datetime.min.replace(tzinfo=timezone.utc),
                d["project_id"],
            ),
        )
        canonical = docs[0]
        canonical_id = canonical["project_id"]
        duplicate_ids = [d["project_id"] for d in docs[1:]]
        await db.runs.update_many({"project_id": {"$in": duplicate_ids}}, {"$set": {"project_id": canonical_id}})
        await db.projects.delete_many({"project_id": {"$in": duplicate_ids}})
        # Ensure the surviving project has a stable key. Keys are generated from the
        # same identity tuple used by this migration.
        key = re.sub(
            r"[^a-z0-9]+", "-",
            f"{group['_id']['name']}-{group['_id']['framework']}".lower(),
        ).strip("-")[:150]
        await db.projects.update_one({"project_id": canonical_id}, {"$set": {"project_key": key}})

    # Backfill keys on all remaining legacy projects before enforcing uniqueness.
    async for project in db.projects.find({"$or": [{"project_key": {"$exists": False}}, {"project_key": None}, {"project_key": ""}]}):
        key = re.sub(r"[^a-z0-9]+", "-", f"{project.get('name', 'project')}-{project.get('framework', 'python')}".lower()).strip("-")[:150]
        await db.projects.update_one({"project_id": project["project_id"]}, {"$set": {"project_key": key}})
