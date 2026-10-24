"""Safe MongoDB connection check. Run from tracelens-backend with its venv active."""
import asyncio
from app.db import client, db

async def main():
    try:
        result = await client.admin.command("ping")
        print("MongoDB ping: PASS")
        print("Database:", db.name)
        print("Result ok:", result.get("ok") == 1.0)
    except Exception as exc:
        # Do not print exception text: it can contain host/URI details.
        print("MongoDB ping: FAIL")
        print("Error type:", type(exc).__name__)
        print("Check Atlas IP access, credentials, URI, DNS, and TLS/network policy.")
        raise SystemExit(1)
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(main())
