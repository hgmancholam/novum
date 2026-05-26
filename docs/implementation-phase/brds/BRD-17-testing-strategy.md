# BRD-17: Testing Strategy & Calibration Eval

**Document ID:** BRD-17
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 18 of 19

---

## 1. Executive Summary

Define the comprehensive testing strategy covering unit tests, integration tests, golden trace fixtures, and RF-16 calibration evaluation. This BRD establishes testing patterns, fixtures, and the evaluation harness for confidence calibration.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-16 | Calibration eval (deferred V2) | Foundation |
| All | Testing requirements | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-01 to BRD-16 | Complete |

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  tests/
    __init__.py
    conftest.py              # Pytest fixtures
    fixtures/
      runs/                  # Golden trace JSONL files
        factual_basic.jsonl
        contradiction.jsonl
        unanswerable.jsonl
      llm_responses/         # Mocked LLM responses
        researcher.json
        judge.json
    unit/
      test_confidence.py
      test_stopping.py
      test_sources.py
      test_events.py
    integration/
      test_api_runs.py
      test_api_events.py
      test_agent_flow.py
    calibration/
      __init__.py
      dataset.py             # Eval dataset loader
      harness.py             # Calibration harness
      metrics.py             # Calibration metrics
frontend/
  src/
    test/
      setup.ts               # Vitest setup
      mocks/
        handlers.ts          # MSW handlers
    components/
      __tests__/             # Co-located tests
```

### 4.2 Backend Test Configuration

#### backend/pyproject.toml (testing section)

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --tb=short"
filterwarnings = [
    "ignore::DeprecationWarning",
]

[tool.coverage.run]
source = ["app"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
fail_under = 80
```

### 4.3 Pytest Fixtures

#### backend/tests/conftest.py

```python
"""Pytest fixtures for backend tests."""

import asyncio
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.main import app
from app.database import Base, get_db
from app.config import settings


# Test database URL (use a separate test database)
TEST_DATABASE_URL = settings.database_url.replace(
    "/novum", "/novum_test"
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session with rollback."""
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
def user_token() -> str:
    """Generate a test user token."""
    from app.services.auth_service import AuthService
    return AuthService.generate_token()


@pytest.fixture
def auth_headers(user_token: str) -> dict:
    """Get authorization headers."""
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def sample_question() -> str:
    """Sample research question."""
    return "When was Tekton Labs founded?"


@pytest.fixture
def sample_run_id() -> str:
    """Sample run UUID."""
    return str(uuid4())
```

### 4.4 Golden Trace Fixtures

#### backend/tests/fixtures/runs/factual_basic.jsonl

```json
{"type": "QuestionAsked", "step_index": 0, "question": "When was Tekton Labs founded?", "question_type": "factual"}
{"type": "PlanCreated", "step_index": 1, "sub_claims": ["Tekton Labs founding year"], "search_queries": ["Tekton Labs founded year", "Tekton Labs company history"]}
{"type": "SourceQueried", "step_index": 2, "source_name": "tavily", "query": "Tekton Labs founded year"}
{"type": "EvidenceCollected", "step_index": 3, "snippets": [{"text": "Tekton Labs was founded in 2013", "source_url": "https://example.com", "confidence": 0.9, "polarity": "supports"}]}
{"type": "JudgeVerdict", "step_index": 4, "confidence": 0.85, "approved": true, "reasoning": "Single reliable source confirms founding year"}
{"type": "ConfidenceCalculated", "step_index": 5, "structural": {"coverage": 1.0, "agreement": 1.0, "diversity": 0.3, "no_conflict": 1.0, "score": 0.83}, "judge": 0.85, "final": 0.83}
{"type": "AnswerDrafted", "step_index": 6, "content": "Tekton Labs was founded in 2013."}
{"type": "Stopped", "step_index": 7, "reason": "judge_confirmed", "final_confidence": 0.83}
```

#### backend/tests/fixtures/runs/contradiction.jsonl

```json
{"type": "QuestionAsked", "step_index": 0, "question": "What year did X happen?", "question_type": "factual"}
{"type": "PlanCreated", "step_index": 1, "sub_claims": ["Year of event X"], "search_queries": ["event X year"]}
{"type": "EvidenceCollected", "step_index": 2, "snippets": [{"text": "X happened in 2020", "source_url": "https://source1.com", "confidence": 0.8, "polarity": "supports"}]}
{"type": "EvidenceCollected", "step_index": 3, "snippets": [{"text": "X occurred in 2019", "source_url": "https://source2.com", "confidence": 0.8, "polarity": "supports"}]}
{"type": "ContradictionDetected", "step_index": 4, "claim": "Year of event X", "sources": ["source1.com", "source2.com"], "values": ["2020", "2019"]}
{"type": "Stopped", "step_index": 5, "reason": "honest_contradiction", "explanation": "Sources provide conflicting years for event X"}
```

### 4.5 Unit Test Examples

#### backend/tests/unit/test_confidence.py

```python
"""Unit tests for confidence calculation."""

import pytest

from app.confidence import (
    ConfidenceCalculator,
    calculate_coverage,
    calculate_agreement,
    calculate_diversity,
    calculate_no_conflict,
)
from app.agent.run_state import RunState, EvidenceItem


class TestCoverageCalculation:
    """Tests for coverage component."""

    def test_full_coverage(self):
        """All claims covered = 1.0."""
        state = RunState(
            sub_claims=["A", "B"],
            covered_claims={"A", "B"},
        )
        assert calculate_coverage(state) == 1.0

    def test_partial_coverage(self):
        """Half claims covered = 0.5."""
        state = RunState(
            sub_claims=["A", "B"],
            covered_claims={"A"},
        )
        assert calculate_coverage(state) == 0.5

    def test_no_claims(self):
        """No claims = 0.0."""
        state = RunState(sub_claims=[], covered_claims=set())
        assert calculate_coverage(state) == 0.0


class TestDiversityCalculation:
    """Tests for source diversity (RF-15)."""

    def test_single_source(self):
        """One domain = 0.3."""
        evidence = [
            EvidenceItem(
                text="Test",
                source_url="https://example.com/page1",
                confidence=0.8,
                polarity="supports",
            ),
            EvidenceItem(
                text="Test2",
                source_url="https://example.com/page2",
                confidence=0.8,
                polarity="supports",
            ),
        ]
        assert calculate_diversity(evidence) == 0.3

    def test_multiple_sources(self):
        """Five domains = 1.0."""
        evidence = [
            EvidenceItem(text="A", source_url="https://a.com", confidence=0.8, polarity="supports"),
            EvidenceItem(text="B", source_url="https://b.com", confidence=0.8, polarity="supports"),
            EvidenceItem(text="C", source_url="https://c.com", confidence=0.8, polarity="supports"),
            EvidenceItem(text="D", source_url="https://d.com", confidence=0.8, polarity="supports"),
            EvidenceItem(text="E", source_url="https://e.com", confidence=0.8, polarity="supports"),
        ]
        assert calculate_diversity(evidence) == 1.0


class TestMinFormula:
    """Tests for min(S, J) formula (RF-12)."""

    def test_structural_lower(self):
        """When S < J, final = S."""
        calculator = ConfidenceCalculator(threshold=0.7)
        state = RunState(
            sub_claims=["A"],
            covered_claims={"A"},
            evidence=[
                EvidenceItem(text="X", source_url="https://x.com", confidence=0.5, polarity="supports")
            ],
        )
        result = calculator.calculate(state, judge_confidence=0.9)
        assert result.final <= result.judge

    def test_judge_lower(self):
        """When J < S, final = J."""
        calculator = ConfidenceCalculator(threshold=0.7)
        state = RunState(
            sub_claims=["A"],
            covered_claims={"A"},
            evidence=[
                EvidenceItem(text="X", source_url="https://x.com", confidence=0.9, polarity="supports"),
                EvidenceItem(text="Y", source_url="https://y.com", confidence=0.9, polarity="supports"),
                EvidenceItem(text="Z", source_url="https://z.com", confidence=0.9, polarity="supports"),
            ],
        )
        result = calculator.calculate(state, judge_confidence=0.5)
        assert result.final == 0.5
```

### 4.6 Integration Test Examples

#### backend/tests/integration/test_api_runs.py

```python
"""Integration tests for runs API."""

import pytest
from httpx import AsyncClient


class TestCreateRun:
    """Tests for POST /api/runs."""

    async def test_create_run_success(self, client: AsyncClient, auth_headers: dict):
        """Successfully create a run."""
        response = await client.post(
            "/api/runs",
            json={"question": "Test question?"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["question"] == "Test question?"
        assert data["status"] == "running"

    async def test_create_run_no_auth(self, client: AsyncClient):
        """Reject without auth."""
        response = await client.post(
            "/api/runs",
            json={"question": "Test?"},
        )
        assert response.status_code == 401

    async def test_create_run_empty_question(self, client: AsyncClient, auth_headers: dict):
        """Reject empty question."""
        response = await client.post(
            "/api/runs",
            json={"question": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestCancelRun:
    """Tests for POST /api/runs/{id}/cancel."""

    async def test_cancel_running(self, client: AsyncClient, auth_headers: dict):
        """Cancel a running run."""
        # Create run
        create_resp = await client.post(
            "/api/runs",
            json={"question": "Test?"},
            headers=auth_headers,
        )
        run_id = create_resp.json()["id"]

        # Cancel
        cancel_resp = await client.post(
            f"/api/runs/{run_id}/cancel",
            headers=auth_headers,
        )
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["stop_reason"] == "user_cancelled"
```

### 4.7 Calibration Evaluation Harness

#### backend/tests/calibration/harness.py

```python
"""Calibration evaluation harness (RF-16 foundation)."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

from app.confidence import ConfidenceCalculator


@dataclass
class EvalQuestion:
    """Single evaluation question."""

    question: str
    expected_answer: str
    expected_confidence_range: tuple[float, float]
    expected_stop_reason: str


@dataclass
class EvalResult:
    """Result of evaluating one question."""

    question: str
    actual_confidence: float
    expected_range: tuple[float, float]
    confidence_in_range: bool
    actual_stop_reason: str
    expected_stop_reason: str
    stop_reason_match: bool


class CalibrationHarness:
    """Harness for confidence calibration evaluation.
    
    Loads a dataset of questions with expected outcomes and
    evaluates the agent's confidence calibration.
    
    Note: Full implementation deferred to V2 per RF-16.
    """

    def __init__(self, dataset_path: Path) -> None:
        self.dataset_path = dataset_path
        self.questions: List[EvalQuestion] = []
        self.results: List[EvalResult] = []

    def load_dataset(self) -> None:
        """Load evaluation dataset from JSONL."""
        with open(self.dataset_path) as f:
            for line in f:
                data = json.loads(line)
                self.questions.append(
                    EvalQuestion(
                        question=data["question"],
                        expected_answer=data["expected_answer"],
                        expected_confidence_range=tuple(data["confidence_range"]),
                        expected_stop_reason=data["stop_reason"],
                    )
                )

    async def evaluate(self) -> dict:
        """Run evaluation on all questions.
        
        Returns metrics dict.
        """
        # Placeholder - full implementation in V2
        return {
            "total_questions": len(self.questions),
            "evaluated": 0,
            "confidence_calibration_error": 0.0,
            "stop_reason_accuracy": 0.0,
        }

    def compute_calibration_error(self) -> float:
        """Compute Expected Calibration Error (ECE).
        
        ECE measures how well confidence scores match actual accuracy.
        """
        if not self.results:
            return 0.0

        # Bin results by confidence
        bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        bin_correct = {i: 0 for i in range(len(bins) - 1)}
        bin_total = {i: 0 for i in range(len(bins) - 1)}
        bin_confidence_sum = {i: 0.0 for i in range(len(bins) - 1)}

        for result in self.results:
            for i in range(len(bins) - 1):
                if bins[i] <= result.actual_confidence < bins[i + 1]:
                    bin_total[i] += 1
                    bin_confidence_sum[i] += result.actual_confidence
                    if result.confidence_in_range:
                        bin_correct[i] += 1
                    break

        # Compute weighted ECE
        total = len(self.results)
        ece = 0.0
        for i in range(len(bins) - 1):
            if bin_total[i] > 0:
                accuracy = bin_correct[i] / bin_total[i]
                avg_confidence = bin_confidence_sum[i] / bin_total[i]
                weight = bin_total[i] / total
                ece += weight * abs(accuracy - avg_confidence)

        return ece
```

### 4.8 Frontend Test Setup

#### frontend/src/test/setup.ts

```typescript
/**
 * Vitest setup file.
 */

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeAll, afterAll } from "vitest";
import { setupServer } from "msw/node";
import { handlers } from "./mocks/handlers";

// Setup MSW server
export const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());
```

#### frontend/src/test/mocks/handlers.ts

```typescript
/**
 * MSW handlers for API mocking.
 */

import { http, HttpResponse } from "msw";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const handlers = [
  // Health check
  http.get(`${API_URL}/api/health`, () => {
    return HttpResponse.json({ status: "ok" });
  }),

  // List runs
  http.get(`${API_URL}/api/runs`, () => {
    return HttpResponse.json({
      items: [
        {
          id: "test-run-1",
          question: "Test question?",
          status: "completed",
          stopReason: "judge_confirmed",
          confidence: 0.85,
          createdAt: new Date().toISOString(),
          eventCount: 7,
          isForked: false,
        },
      ],
      total: 1,
      hasMore: false,
    });
  }),

  // Create run
  http.post(`${API_URL}/api/runs`, async ({ request }) => {
    const body = await request.json() as { question: string };
    return HttpResponse.json(
      {
        id: "new-run-id",
        question: body.question,
        status: "running",
      },
      { status: 201 }
    );
  }),

  // Get run
  http.get(`${API_URL}/api/runs/:runId`, ({ params }) => {
    return HttpResponse.json({
      id: params.runId,
      question: "Test question?",
      status: "completed",
      stopReason: "judge_confirmed",
      confidence: 0.85,
      threshold: 0.7,
      createdAt: new Date().toISOString(),
    });
  }),

  // Formats
  http.get(`${API_URL}/api/formats`, () => {
    return HttpResponse.json({
      formats: [
        { name: "prose", display: "Prose" },
        { name: "structured", display: "Structured" },
      ],
    });
  }),
];
```

---

## 5. Acceptance Criteria

### AC-01: Unit Tests Pass
```gherkin
Given the test suite
When I run `pytest tests/unit/`
Then all unit tests pass
  And coverage is >= 80%
```

### AC-02: Integration Tests Pass
```gherkin
Given the test suite
When I run `pytest tests/integration/`
Then all API tests pass
  And database rollbacks work correctly
```

### AC-03: Golden Traces Validate
```gherkin
Given golden trace fixtures
When I load them into the test database
When I replay events through the system
Then the output matches expected behavior
```

### AC-04: Frontend Tests Pass
```gherkin
Given the frontend test suite
When I run `npm test`
Then all component tests pass
  And MSW mocks work correctly
```

---

## 6. Implementation Checklist

- [ ] Create `backend/tests/conftest.py`
- [ ] Create golden trace fixtures in `backend/tests/fixtures/runs/`
- [ ] Create `backend/tests/unit/test_confidence.py`
- [ ] Create `backend/tests/unit/test_stopping.py`
- [ ] Create `backend/tests/integration/test_api_runs.py`
- [ ] Create `backend/tests/calibration/harness.py`
- [ ] Create `frontend/src/test/setup.ts`
- [ ] Create `frontend/src/test/mocks/handlers.ts`
- [ ] Update `pyproject.toml` with pytest config
- [ ] Update `vite.config.ts` with test config
- [ ] Run full test suite and fix failures

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit | pytest | Business logic | 100% |
| Integration | pytest + httpx | API endpoints | 100% |
| Component | Vitest + RTL | React components | 100% |
| E2E | Playwright (V2) | Full flows | Deferred |

## 8. Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TEST_DATABASE_URL` | Yes | Test database connection |

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Tests slow CI | Med | Med | Parallel execution |
| Flaky async tests | High | Med | Proper fixtures/cleanup |

## 10. Out of Scope

- E2E tests (V2)
- Visual regression tests
- Performance benchmarks
- Full calibration eval (V2)
