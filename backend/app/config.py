"""Application configuration via environment variables."""

from pydantic import SecretStr
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

    # LLM — provider selection (single active provider at runtime).
    # Switch with one env var; all four roles route through it.
    # Accepted values: "github" | "openai" | "anthropic" | "google".
    llm_provider: str = "github"

    # GitHub Models (default provider; rate-limited so token+model pools exist)
    github_token: str
    # Optional comma-separated pool of GitHub PATs for per-call round-robin
    # rotation. Each PAT has its own rate-limit bucket, so N tokens give
    # N x effective RPM. When empty, falls back to ``github_token``.
    github_tokens: str = ""
    llm_api_base: str = "https://models.github.ai/inference"
    llm_model_classifier: str = "meta/Llama-4-Scout-17B-16E-Instruct"
    llm_model_planner: str = "deepseek/DeepSeek-V3-0324"
    llm_model_synthesizer: str = "openai/gpt-5"
    llm_model_judge: str = "deepseek/DeepSeek-V3-0324"

    # Alternative providers — one model per provider applies to all 4 roles.
    # Per-role overrides via `<provider>_model_<role>` (optional, blank = use default).
    # IDs are litellm-compatible. Override via env if a model is renamed upstream.
    openai_model: str = "gpt-5.4"
    openai_model_classifier: str = ""
    openai_model_planner: str = ""
    openai_model_synthesizer: str = ""
    openai_model_judge: str = ""

    anthropic_model: str = "anthropic/claude-sonnet-4-6"
    anthropic_model_classifier: str = ""
    anthropic_model_planner: str = ""
    anthropic_model_synthesizer: str = ""
    anthropic_model_judge: str = ""

    google_model: str = "gemini/gemini-2.5-flash"
    google_api_key: SecretStr | None = None
    google_model_classifier: str = ""
    google_model_planner: str = ""
    google_model_synthesizer: str = ""
    google_model_judge: str = ""

    # Optional comma-separated model pools per role for round-robin rotation
    # (mitigates GitHub Models per-model per-minute quotas). When empty, the
    # single ``llm_model_<role>`` value above is used.
    llm_model_classifier_pool: str = ""
    llm_model_planner_pool: str = ""
    llm_model_synthesizer_pool: str = ""
    llm_model_judge_pool: str = ""

    # WP-5: Judge provider routing (default "github" since no Anthropic key in prod)
    judge_provider: str = "github"  # "anthropic" or "github"
    judge_model: str = "deepseek/DeepSeek-V3-0324"  # GitHub fallback model
    anthropic_api_key: SecretStr | None = None

    # Search
    tavily_api_key: str

    # WP-4: Embeddings (for saturation signal novelty computation)
    embedding_model: str = "openai/text-embedding-3-small"
    openai_api_key: SecretStr | None = None

    # WP-4: Saturation signal thresholds
    # floor < 0.1 → system never saturates on broad questions (too strict);
    # floor > 0.25 → false positives on rich corpora (too loose).
    novelty_floor: float = 0.15
    saturation_window: int = 3  # k=3 most recent chunks for novelty computation

    # WP-4: Budget audit (G11) — matrix row 7 (memory of agents) needs ~8 rounds
    # to saturate; row 8 (long-term risks) needs similar depth.
    max_rounds: int = 20  # increased from 10 to allow deep exploration
    max_searches_per_round: int = 5  # increased from 3 for broader coverage
    max_tokens_per_run: int = 150_000  # increased from 100k for complex synthesis

    # WP-6: Cross-run question memory
    prior_run_index_cap: int = 256  # LRU cap on in-memory question index

    # BRD-22: Complexity-aware planning thresholds
    complexity_max_trivial_words: int = 8
    complexity_min_trivial_confidence: float = 0.80
    complexity_min_deep_words: int = 16
    complexity_max_deep_confidence: float = 0.55

    # BRD-22: Instant-answer cache
    instant_cache_min_confidence: float = 0.85
    instant_cache_max_size: int = 256

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # CORS: comma-separated list of allowed origins (e.g. "https://novum.vercel.app,http://localhost:5173")
    cors_origins: str = "https://novum-seven.vercel.app,http://localhost:5173"

    # SSE
    sse_heartbeat_seconds: int = 15

    # WP-3 G8: Early-stop thresholds for trivial-fact questions (matrix row 1).
    # When coverage == 1.0 AND C_agreement >= 0.9 AND J >= 0.85 on round 1,
    # stop immediately with judge_confirmed to avoid unnecessary iterations.
    early_stop_min_agreement: float = 0.9
    early_stop_min_judge: float = 0.85

    # BRD-23 WP-1: stale-citation kind-ceiling penalty multiplier for AnswerKind.DIRECT
    # when temporal_sensitivity is volatile/realtime and >=50% citations are stale.
    temporal_stale_penalty: float = 0.85

    # BRD-23 WP-3: authority-tier multipliers applied inside C_coverage / C_diversity.
    authority_multiplier_primary: float = 1.05
    authority_multiplier_reputable: float = 1.00
    authority_multiplier_general: float = 0.90
    authority_multiplier_low: float = 0.50

    # BRD-23 WP-2: deep-fetch escalation budget and thresholds.
    deep_fetch_min_snippet_chars: int = 400
    deep_fetch_top_k: int = 2
    deep_fetch_timeout_s: float = 10.0
    deep_fetch_max_per_run_trivial: int = 0
    deep_fetch_max_per_run_standard: int = 2
    deep_fetch_max_per_run_deep: int = 3

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()  # pyright: ignore[reportCallIssue]
