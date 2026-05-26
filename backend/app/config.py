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
    llm_api_base: str = "https://models.github.ai/inference"
    llm_model_classifier: str = "meta/Llama-4-Scout-17B-16E-Instruct"
    llm_model_planner: str = "deepseek/DeepSeek-V3-0324"
    llm_model_synthesizer: str = "openai/gpt-5"
    llm_model_judge: str = "deepseek/DeepSeek-V3-0324"

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


settings = Settings()  # pyright: ignore[reportCallIssue]
