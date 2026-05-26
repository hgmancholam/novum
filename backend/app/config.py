"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/novum"

    # LLM
    github_token: str
    llm_model_researcher: str = "gpt-4o"
    llm_model_judge: str = "o1-mini"
    llm_model_planner: str = "gpt-4o-mini"
    llm_model_critic: str = "gpt-4o-mini"

    # Search
    tavily_api_key: str

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # SSE
    sse_heartbeat_seconds: int = 15


settings = Settings()
