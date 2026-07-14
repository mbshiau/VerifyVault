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
    cors_origin: str = "http://localhost:3000"


settings = Settings()
