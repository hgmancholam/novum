"""Application configuration via environment variables."""

from pydantic import SecretStr, model_validator
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
    # V1 lock: only ``anthropic`` is permitted unless ``allow_non_anthropic_providers``
    # is explicitly enabled (see validator below + ai-services.md §1.2).
    # The interface still supports ``github`` | ``openai`` | ``anthropic`` | ``google``
    # so re-enabling cross-family routing is a one-env-var change.
    llm_provider: str = "anthropic"

    # V1 doctrine escape hatch — set to ``true`` ONLY to re-enable cross-family
    # providers (GitHub Models, OpenAI direct, Google Gemini) for Plan-B outages
    # or test fixtures. Production deploys must keep this False.
    allow_non_anthropic_providers: bool = False

    # GitHub Models (wired-but-disabled in V1; required for Plan-B fallback)
    github_token: str = ""
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

    # Anthropic Claude — V1 active provider.
    # Per-role defaults follow ai-services.md §1.3: haiku-4-5 for the cheap
    # classifier path, sonnet-4-6 for everything else. All overridable via env
    # (ANTHROPIC_MODEL_CLASSIFIER, ANTHROPIC_MODEL_PLANNER, …).
    anthropic_model: str = "anthropic/claude-sonnet-4-6"
    anthropic_model_classifier: str = "anthropic/claude-haiku-4-5"
    anthropic_model_planner: str = "anthropic/claude-sonnet-4-6"
    anthropic_model_synthesizer: str = "anthropic/claude-sonnet-4-6"
    anthropic_model_judge: str = "anthropic/claude-sonnet-4-6"

    google_model: str = "gemini/gemini-2.5-flash"
    google_api_key: SecretStr | None = None
    google_model_classifier: str = ""
    google_model_planner: str = ""
    google_model_synthesizer: str = ""
    google_model_judge: str = ""

    # Optional comma-separated model pools per role for round-robin rotation
    # (mitigates GitHub Models per-model per-minute quotas). When empty, the
    # single ``llm_model_<role>`` value above is used. V1 unused (Anthropic
    # has no per-model RPM split needing rotation) — kept for Plan-B.
    llm_model_classifier_pool: str = ""
    llm_model_planner_pool: str = ""
    llm_model_synthesizer_pool: str = ""
    llm_model_judge_pool: str = ""

    # WP-5: Judge provider routing. V1 default = anthropic (single active provider).
    judge_provider: str = "anthropic"  # "anthropic" or "github"
    judge_model: str = "anthropic/claude-sonnet-4-6"
    anthropic_api_key: SecretStr | None = None

    # Search
    tavily_api_key: str
    # Optional Semantic Scholar key — free tier works without one but is rate-limited.
    semantic_scholar_api_key: SecretStr | None = None
    # Optional contact email for OpenAlex "polite pool" (faster, more reliable).
    # OpenAlex has no API key; passing ``mailto`` is the recommended courtesy.
    openalex_email: str = ""
    # Optional OpenAlex premium key — sent as ``api_key=`` query param.
    # Raises rate limits above the anonymous tier.
    openalex_api_key: SecretStr | None = None

    # BRD-29: USD per Tavily credit (basic=1 credit, advanced=2 credits).
    tavily_usd_per_credit: float = 0.008

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

    # Global confidence threshold (RF-12). Server-controlled — the UI no longer
    # exposes a per-run picker. Applied to every new run unless the request body
    # explicitly overrides it (kept optional for parity with stored history).
    confidence_threshold_default: float = 0.5

    # IP-26 / BRD-26 Area 6: reflective meta-judge.
    # PR-2 (post-2026-05-29 eval): enabled by default. Unit tests that need
    # the legacy behaviour set this to False explicitly via env or monkeypatch.
    meta_judge_enabled: bool = True
    meta_judge_min_delta_s: float = 0.03
    # Post-PR-7: required `expected_delta_s` grows with the round index so
    # the meta-judge gets stricter as the run drags on. From round
    # ``meta_judge_delta_growth_start`` onwards, the required delta becomes
    # ``min(meta_judge_min_delta_s + (round - start) * growth, cap)``.
    meta_judge_delta_growth_start: int = 3
    meta_judge_delta_growth_per_round: float = 0.02
    meta_judge_delta_cap: float = 0.15

    # PR-2 Mejora 2.5: minimum evidence count required before the new
    # `before_synthesizing` hook is allowed to fire mid-flow. Prevents the
    # meta-judge from being called on near-empty evidence sets (where the
    # decision is trivially "continue").
    meta_judge_before_synth_min_evidence: int = 20

    # BRD-26 §4.13: cost gate for the DEEP `after_react_observation` hook
    # (slice 3b'). Default OFF so behaviour is unchanged on merge; flip via
    # env (`META_JUDGE_AFTER_REACT_ENABLED=true`) after the shadow window.
    # The cap is shared across all three hooks (after_judge, after_cove,
    # after_react_observation) to keep total meta-judge cost bounded.
    meta_judge_after_react_enabled: bool = False
    meta_judge_react_warmup_steps: int = 2
    max_meta_judge_calls_per_run: int = 4

    # Post-PR-7: stuck-planner detector. Fires when two consecutive
    # reformulation generations return roughly the same top URLs
    # (Jaccard overlap >= threshold). Forces a deadline draft before the
    # numeric budget runs out on a planner that has stopped diversifying.
    stuck_planner_enabled: bool = True
    stuck_planner_min_overlap: float = 0.6
    stuck_planner_min_urls_per_gen: int = 3

    # Post-PR-8 token optimization. Cache the long stable role system prompts
    # on Anthropic's side (5-min ephemeral TTL, billed at 10% of base input
    # tokens). Enabled by default; disable via env if a future provider
    # rejects the ``cache_control`` block. Zero behavioral change — same
    # tokens reach the model, only the transport bills less.
    anthropic_prompt_cache_enabled: bool = True
    # In-process exact-match cache for CLASSIFIER calls only (deterministic
    # categorical output → safe to memoize). Other roles intentionally skip
    # the cache so research stays fresh per run.
    classifier_cache_enabled: bool = True
    classifier_cache_ttl_seconds: int = 86_400
    classifier_cache_max_entries: int = 1_000

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

    # PR-1 (post-2026-05-29 eval): hard global stop guards per lane. These are
    # FSM-independent — enforced at the top of the orchestrator loop, so a run
    # cannot hang in SEARCHING↔ANALYZING forever. Units: seconds for wall_clock,
    # event counts for the rest. See docs/evaluation/2026-05-29-agent-evaluation-and-comparison.md
    wall_clock_max_s_fast: int = 60
    wall_clock_max_s_standard: int = 300
    wall_clock_max_s_deep: int = 600
    max_tool_calls_fast: int = 8
    max_tool_calls_standard: int = 25
    max_tool_calls_deep: int = 60
    max_evidence_fast: int = 15
    max_evidence_standard: int = 60
    max_evidence_deep: int = 150
    # Overridable via env (pydantic-settings maps field name → uppercase var,
    # e.g. MAX_QUERY_REFORMULATIONS_STANDARD). Bumped after the 2026-05-29
    # eval where Q2/Q6 hit the cap at 5 and stopped with stopped_by_budget.
    max_query_reformulations_fast: int = 1
    max_query_reformulations_standard: int = 8
    max_query_reformulations_deep: int = 15
    # Event-level plateau window: if the last N emitted events contain ZERO
    # progress markers (ClaimCovered, DraftSynthesized, JudgeRuled, PlanGapsDetected,
    # HypothesisEvaluated) the run is stuck and we stop with stopped_by_budget.
    no_progress_event_window: int = 30

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _enforce_v1_anthropic_only(self) -> "Settings":
        """V1 doctrine guard: lock the active LLM provider to Anthropic.

        The interface in ``app/llm/`` is provider-agnostic (litellm supports
        Anthropic, OpenAI, Google Gemini and GitHub Models) but V1 only
        activates Anthropic Claude. To re-enable any other provider — for
        a Plan-B outage swap or a cross-family R6 mitigation experiment —
        set ``ALLOW_NON_ANTHROPIC_PROVIDERS=true`` explicitly.

        See: ai-services.md §1.2 / §1.3.
        """
        if self.allow_non_anthropic_providers:
            return self
        if self.llm_provider != "anthropic":
            raise ValueError(
                f"V1: LLM_PROVIDER must be 'anthropic' (got {self.llm_provider!r}). "
                "Set ALLOW_NON_ANTHROPIC_PROVIDERS=true to override (Plan-B only)."
            )
        if self.judge_provider != "anthropic":
            raise ValueError(
                f"V1: JUDGE_PROVIDER must be 'anthropic' (got {self.judge_provider!r}). "
                "Set ALLOW_NON_ANTHROPIC_PROVIDERS=true to override (Plan-B only)."
            )
        if self.anthropic_api_key is None:
            raise ValueError(
                "V1: ANTHROPIC_API_KEY is required (LLM_PROVIDER=anthropic). "
                "Set ALLOW_NON_ANTHROPIC_PROVIDERS=true to boot without it."
            )
        return self


settings = Settings()  # pyright: ignore[reportCallIssue]
