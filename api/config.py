from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/verifyvault"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-oss-120b"
    tavily_api_key: str = ""
    # Kept as a raw comma-separated string (not list[str]) since this
    # pydantic-settings version JSON-decodes complex-typed env vars by
    # default, which chokes on a plain comma-separated value.
    cors_origin: str = "http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:5173,http://localhost:5173"

    # Video upload/transcription
    groq_whisper_model: str = "whisper-large-v3"
    video_storage_dir: str = "uploads/videos"
    video_max_size_mb: int = 500
    video_max_duration_seconds: int = 7200

    # Auth
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    session_secret: str = "dev-session-secret-change-me"

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    frontend_url: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origin.split(",") if origin.strip()]


settings = Settings()
