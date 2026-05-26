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

    # CORS: comma-separated list of allowed origins (e.g. "https://novum.vercel.app,http://localhost:5173")
    cors_origins: str = "https://novum-seven.vercel.app,http://localhost:5173"

    # SSE
    sse_heartbeat_seconds: int = 15

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
