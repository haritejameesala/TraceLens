from pydantic_settings import BaseSettings, SettingsConfigDict
from pymongo import MongoClient
import certifi

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    mongodb_uri: str
    mongodb_database: str

settings = Settings()

client = MongoClient(
    settings.mongodb_uri,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=15000,
)

try:
    print(client.admin.command("ping"))
    print("MongoDB Atlas connection successful")
    print("Database:", settings.mongodb_database)
except Exception as exc:
    print(type(exc).__name__, exc)
finally:
    client.close()