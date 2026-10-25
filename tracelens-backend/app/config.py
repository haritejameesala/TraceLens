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
    # JSON mapping of project_id to SDK ingestion secret. Example: {"proj_abc":"long-random-secret"}
    tracelens_sdk_keys: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


    google_client_id: str = ""
    google_client_secret: str = ""
    auth_mode: str = "disabled"  # could be 'google' or 'disabled'
    frontend_origin: str = "http://localhost:3000"

    github_client_id: str = ""
    github_client_secret: str = ""
    
settings = Settings()
