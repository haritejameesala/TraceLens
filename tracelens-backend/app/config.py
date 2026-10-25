from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "tracelens"
    mongodb_tls_ca_file: str | None = None
    mongo_server_selection_timeout_ms: int = 5000
    rca_provider: str = "ollama"
    rca_ollama_base_url: str = "http://127.0.0.1:11434"
    rca_ollama_model: str = "qwen2.5:3b"
    rca_timeout_seconds: float = 45.0
    auth_secret: str = ""
    frontend_url: str = "http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
