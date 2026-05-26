# BRD-05: LLM Client Integration

**Document ID:** BRD-05
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 6 of 19

---

## 1. Executive Summary

Implement the LLM client layer using litellm + instructor for structured outputs. This BRD defines the 4 LLM roles (Researcher, Judge, Planner, Critic) with their model assignments, prompt templates, and retry logic via tenacity.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-12 | Judge LLM for confidence evaluation | Complete |
| RF-14 | Plan critic (up to 2 attempts) | Complete |
| RF-15 | Cross-family judge requirement | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-00, BRD-02 | BRD-07, BRD-08, BRD-09 |

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    llm/
      __init__.py
      client.py            # Main LLM client
      models.py            # LLM request/response models
      prompts.py           # System prompts for each role
      roles.py             # Role definitions
      retry.py             # Tenacity retry configuration
```

### 4.2 LLM Roles & Models

| Role | Model | Purpose | Family |
|------|-------|---------|--------|
| Researcher | gpt-4o | Main research agent, evidence analysis | OpenAI |
| Judge | o1-mini | Answer quality evaluation | OpenAI (reasoning) |
| Planner | gpt-4o-mini | Sub-claim decomposition | OpenAI |
| Critic | gpt-4o-mini | Plan quality critique | OpenAI |

> Per RF-15: Judge uses a different model family (reasoning model) for independence.

### 4.3 Role Definitions

#### backend/app/llm/roles.py

```python
"""LLM role definitions and model assignments."""

from enum import StrEnum
from typing import NamedTuple


class LLMRole(StrEnum):
    """LLM roles in the research agent."""

    RESEARCHER = "researcher"
    JUDGE = "judge"
    PLANNER = "planner"
    CRITIC = "critic"


class RoleConfig(NamedTuple):
    """Configuration for an LLM role."""

    model: str
    temperature: float
    max_tokens: int
    description: str


# Default role configurations
# Can be overridden by environment variables
ROLE_CONFIGS: dict[LLMRole, RoleConfig] = {
    LLMRole.RESEARCHER: RoleConfig(
        model="gpt-4o",
        temperature=0.3,
        max_tokens=4096,
        description="Main research agent for evidence analysis",
    ),
    LLMRole.JUDGE: RoleConfig(
        model="o1-mini",
        temperature=0.0,  # Deterministic for reproducibility
        max_tokens=2048,
        description="Cross-family judge for answer evaluation (RF-15)",
    ),
    LLMRole.PLANNER: RoleConfig(
        model="gpt-4o-mini",
        temperature=0.2,
        max_tokens=2048,
        description="Sub-claim decomposition planner",
    ),
    LLMRole.CRITIC: RoleConfig(
        model="gpt-4o-mini",
        temperature=0.3,
        max_tokens=1024,
        description="Plan quality critic (RF-14)",
    ),
}
```

### 4.4 Retry Configuration

#### backend/app/llm/retry.py

```python
"""Tenacity retry configuration for LLM calls."""

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)
import structlog
import httpx

logger = structlog.get_logger()

# Retryable exceptions
RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.HTTPStatusError,  # Includes 429, 500, 503
)


def create_retry_decorator(max_attempts: int = 3):
    """Create a retry decorator for LLM calls.
    
    Uses exponential backoff: 1s, 2s, 4s
    """
    return retry(
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before_sleep=before_sleep_log(logger, "warning"),
        reraise=True,
    )


# Pre-configured decorators
retry_llm = create_retry_decorator(max_attempts=3)
retry_llm_critical = create_retry_decorator(max_attempts=5)
```

### 4.5 LLM Response Models

#### backend/app/llm/models.py

```python
"""Pydantic models for structured LLM outputs."""

from typing import Optional
from pydantic import BaseModel, Field


# =============================================================================
# Planner Outputs
# =============================================================================


class SubClaimOutput(BaseModel):
    """A sub-claim from the planner."""

    id: str = Field(..., description="Unique identifier like 'c1', 'c2'")
    text: str = Field(..., description="The sub-claim statement")
    rationale: str = Field(..., description="Why this claim is needed")


class PlanOutput(BaseModel):
    """Structured plan from the planner."""

    sub_claims: list[SubClaimOutput] = Field(..., min_length=1, max_length=10)
    overall_rationale: str = Field(..., description="How these claims answer the question")


# =============================================================================
# Critic Outputs
# =============================================================================


class CritiqueOutput(BaseModel):
    """Critique from the plan critic."""

    acceptable: bool = Field(..., description="Is the plan acceptable?")
    issues: list[str] = Field(default_factory=list, description="List of issues found")
    suggested_changes: list[str] = Field(default_factory=list)
    summary: str = Field(..., description="Brief summary of the critique")


# =============================================================================
# Researcher Outputs
# =============================================================================


class SearchQueryOutput(BaseModel):
    """Search query generated by the researcher."""

    query: str = Field(..., description="The search query to execute")
    intent: str = Field(..., description="Why this query will help")
    target_claim_id: Optional[str] = Field(None, description="Which claim this targets")


class EvidenceAnalysis(BaseModel):
    """Analysis of a piece of evidence."""

    relevant: bool = Field(..., description="Is this evidence relevant?")
    polarity: str = Field(..., description="supports/contradicts/neutral")
    confidence: float = Field(..., ge=0.0, le=1.0)
    extracted_fact: str = Field(..., description="Key fact from the evidence")
    reasoning: str = Field(..., description="Why this conclusion")


class AnswerDraft(BaseModel):
    """Draft answer from the researcher."""

    prose: str = Field(..., description="Natural language answer")
    key_points: list[str] = Field(..., description="Main points covered")
    confidence_estimate: float = Field(..., ge=0.0, le=1.0)
    gaps: list[str] = Field(default_factory=list, description="Known gaps in evidence")


# =============================================================================
# Judge Outputs
# =============================================================================


class JudgeVerdict(BaseModel):
    """Verdict from the judge LLM."""

    confidence: float = Field(..., ge=0.0, le=1.0, description="Judge confidence J")
    verdict: str = Field(..., description="approve/reject/needs_revision")
    rationale: str = Field(..., description="Explanation of the verdict")
    improvements: list[str] = Field(default_factory=list, description="Suggested improvements")
    factual_errors: list[str] = Field(default_factory=list, description="Factual issues found")
```

### 4.6 System Prompts

#### backend/app/llm/prompts.py

```python
"""System prompts for each LLM role."""

PLANNER_SYSTEM_PROMPT = """You are a research planning assistant. Your job is to decompose questions into verifiable sub-claims.

Guidelines:
1. Each sub-claim should be independently verifiable
2. Sub-claims should be mutually exclusive and collectively exhaustive
3. Prefer 3-7 sub-claims per question
4. Each sub-claim should be factual, not speculative
5. Number sub-claims as c1, c2, c3, etc.

Output format: JSON matching the PlanOutput schema."""

CRITIC_SYSTEM_PROMPT = """You are a plan quality critic. Evaluate research plans for completeness and feasibility.

Check for:
1. Are all sub-claims verifiable with web search or Wikipedia?
2. Are there logical gaps between sub-claims and the main question?
3. Are any sub-claims redundant?
4. Are the sub-claims appropriately scoped (not too broad, not too narrow)?

Be constructive. If the plan is acceptable, say so. If not, provide specific improvements.

Output format: JSON matching the CritiqueOutput schema."""

RESEARCHER_SYSTEM_PROMPT = """You are a research agent gathering evidence to answer questions.

When generating search queries:
1. Be specific and targeted
2. Include relevant keywords from the claim
3. Prefer queries that will return authoritative sources
4. Avoid yes/no queries - seek factual information

When analyzing evidence:
1. Distinguish between primary sources and secondary sources
2. Note the publication date and source authority
3. Extract specific facts, not opinions
4. Note contradictions between sources

When drafting answers:
1. Cite evidence explicitly
2. Acknowledge uncertainty when present
3. Do not speculate beyond the evidence
4. Use neutral, objective language

Reply in the same language the user used (Spanish by default for user-facing content).

Output format: JSON matching the requested schema."""

JUDGE_SYSTEM_PROMPT = """You are an independent judge evaluating research answers for quality and accuracy.

Your role is critical: you must catch errors, omissions, and unsupported claims.

Evaluation criteria:
1. **Factual accuracy**: Are all claims supported by cited evidence?
2. **Completeness**: Does the answer fully address the question?
3. **Source quality**: Are sources authoritative and current?
4. **Logical coherence**: Does the reasoning follow from the evidence?
5. **Honesty**: Are limitations and uncertainties acknowledged?

Scoring:
- confidence 0.9-1.0: Excellent, ready to publish
- confidence 0.7-0.89: Good, minor improvements needed
- confidence 0.5-0.69: Acceptable but has gaps
- confidence < 0.5: Needs significant revision

Be rigorous. Your job is to protect users from incorrect information.

Output format: JSON matching the JudgeVerdict schema."""
```

### 4.7 Main LLM Client

#### backend/app/llm/client.py

```python
"""LLM client for structured outputs via litellm + instructor."""

from typing import TypeVar, Type
import instructor
import litellm
from pydantic import BaseModel
import structlog

from app.config import settings
from app.llm.roles import LLMRole, ROLE_CONFIGS
from app.llm.prompts import (
    PLANNER_SYSTEM_PROMPT,
    CRITIC_SYSTEM_PROMPT,
    RESEARCHER_SYSTEM_PROMPT,
    JUDGE_SYSTEM_PROMPT,
)
from app.llm.retry import retry_llm

logger = structlog.get_logger()

# Type variable for structured output
T = TypeVar("T", bound=BaseModel)

# Configure litellm for GitHub Models
litellm.api_base = "https://models.inference.ai.azure.com"
litellm.api_key = settings.github_token

# Create instructor-patched client
client = instructor.from_litellm(litellm.acompletion)


# Role to prompt mapping
ROLE_PROMPTS: dict[LLMRole, str] = {
    LLMRole.PLANNER: PLANNER_SYSTEM_PROMPT,
    LLMRole.CRITIC: CRITIC_SYSTEM_PROMPT,
    LLMRole.RESEARCHER: RESEARCHER_SYSTEM_PROMPT,
    LLMRole.JUDGE: JUDGE_SYSTEM_PROMPT,
}


class LLMClient:
    """Client for making structured LLM calls."""

    @retry_llm
    async def call(
        self,
        role: LLMRole,
        user_message: str,
        response_model: Type[T],
        context: str | None = None,
    ) -> T:
        """Make a structured LLM call.
        
        Args:
            role: The LLM role to use
            user_message: The user/task message
            response_model: Pydantic model for structured output
            context: Optional additional context
            
        Returns:
            Parsed response matching response_model
        """
        config = ROLE_CONFIGS[role]
        system_prompt = ROLE_PROMPTS[role]

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        if context:
            messages.append({"role": "user", "content": f"Context:\n{context}"})

        messages.append({"role": "user", "content": user_message})

        logger.debug(
            "llm_call_start",
            role=role,
            model=config.model,
            response_model=response_model.__name__,
        )

        result = await client.chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            response_model=response_model,
        )

        logger.debug(
            "llm_call_complete",
            role=role,
            model=config.model,
        )

        return result

    async def count_tokens(self, text: str, model: str = "gpt-4o") -> int:
        """Count tokens in text using tiktoken."""
        import tiktoken

        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")

        return len(encoding.encode(text))


# Singleton instance
llm = LLMClient()
```

### 4.8 Package Init

#### backend/app/llm/__init__.py

```python
"""LLM client package."""

from app.llm.client import llm, LLMClient
from app.llm.roles import LLMRole, ROLE_CONFIGS, RoleConfig
from app.llm.models import (
    PlanOutput,
    SubClaimOutput,
    CritiqueOutput,
    SearchQueryOutput,
    EvidenceAnalysis,
    AnswerDraft,
    JudgeVerdict,
)

__all__ = [
    "llm",
    "LLMClient",
    "LLMRole",
    "ROLE_CONFIGS",
    "RoleConfig",
    "PlanOutput",
    "SubClaimOutput",
    "CritiqueOutput",
    "SearchQueryOutput",
    "EvidenceAnalysis",
    "AnswerDraft",
    "JudgeVerdict",
]
```

---

## 5. Acceptance Criteria

### AC-01: Planner Produces Valid Plan
```gherkin
Given question "When was Tekton Labs founded?"
When I call llm.call(PLANNER, question, PlanOutput)
Then a PlanOutput is returned
  And it contains 1-10 sub_claims
  And each sub_claim has id, text, and rationale
```

### AC-02: Critic Evaluates Plan
```gherkin
Given a PlanOutput with sub_claims
When I call llm.call(CRITIC, plan_json, CritiqueOutput)
Then a CritiqueOutput is returned
  And it contains acceptable (bool)
  And if not acceptable, issues is non-empty
```

### AC-03: Judge Returns Confidence
```gherkin
Given a draft answer with evidence
When I call llm.call(JUDGE, answer_json, JudgeVerdict)
Then a JudgeVerdict is returned
  And confidence is between 0.0 and 1.0
  And verdict is one of "approve", "reject", "needs_revision"
```

### AC-04: Retry on Transient Errors
```gherkin
Given the LLM API returns 429 (rate limited)
When I make an LLM call
Then the call is retried with exponential backoff
  And after 3 failures, the exception is raised
```

### AC-05: Token Counting Works
```gherkin
Given text "Hello world"
When I call llm.count_tokens(text)
Then a positive integer is returned
```

---

## 6. Implementation Checklist

- [ ] Create `backend/app/llm/__init__.py`
- [ ] Create `backend/app/llm/roles.py`
- [ ] Create `backend/app/llm/retry.py`
- [ ] Create `backend/app/llm/models.py`
- [ ] Create `backend/app/llm/prompts.py`
- [ ] Create `backend/app/llm/client.py`
- [ ] Update `backend/app/config.py` with LLM model settings
- [ ] Write unit tests with mocked responses
- [ ] Write integration test with real API (manual)
- [ ] Verify structured output parsing

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit | pytest + pytest-httpx | Client with mocked API | 100% |
| Unit | pytest | Token counting | 100% |
| Unit | pytest | Retry logic | 100% |
| Integration | Manual | Real API calls | Smoke test |

## 8. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITHUB_TOKEN` | Yes | — | GitHub PAT for Models API |
| `LLM_MODEL_RESEARCHER` | No | `gpt-4o` | Model for researcher |
| `LLM_MODEL_JUDGE` | No | `o1-mini` | Model for judge |
| `LLM_MODEL_PLANNER` | No | `gpt-4o-mini` | Model for planner |
| `LLM_MODEL_CRITIC` | No | `gpt-4o-mini` | Model for critic |

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| API rate limiting | Med | High | Retry with backoff, queue requests |
| Model output format changes | High | Low | Instructor handles schema enforcement |
| Token budget exceeded | Med | Medium | Track tokens, truncate context |
| GitHub Models unavailable | High | Low | Single provider in V1; fallback in V2 |

## 10. Out of Scope

- Multiple LLM providers (V2)
- Fine-tuned models
- Caching layer for responses
- Streaming responses (SSE handles final delivery)
- Token budget management (BRD-09)
