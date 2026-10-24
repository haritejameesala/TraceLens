import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient(
        "mongodb://127.0.0.1:27017",
        tls=False,
        serverSelectionTimeoutMS=5000,
    )
    try:
        print(await client.admin.command("ping"))
    finally:
        client.close()

asyncio.run(main())
