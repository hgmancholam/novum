# Implementation Plan: BRD-07 Agent FSM & Research Loop

**Plan ID:** IP-07
**BRD Reference:** [BRD-07-agent-fsm.md](../brds/BRD-07-agent-fsm.md)
**Created:** 2026-05-26
**Status:** Ready for Coder
**Implementation Order:** 8 of 19

---

## 1. Overview

Implement the **Agent FSM** that orchestrates the full research loop:

```
INIT → PLANNING → CRITIQUING → (REVISING)* → SEARCHING ⇄ ANALYZING → DRAFTING → JUDGING → STOPPED
                                                                                       ↘ SEARCHING (re-search if judge rejects)
```

The orchestrator is **pure in-memory**: it owns a `RunState` Pydantic model and emits `BaseEvent` instances through an injected async callback. **It does not persist events, does not stream over SSE, and does not implement the layered stopping policy** — those concerns belong to BRD-09 (stopping signals), BRD-10 (SSE streaming) and the run worker that wires the orchestrator to the DB. This is the **engine**; later BRDs wire it to the world.

This BRD is the **first one that touches every other backend module already shipped** (BRD-02 events, BRD-05 LLM client, BRD-06 sources), so the plan is unusually detailed: small misalignments produce silent data-shape drift between events on the wire and the FSM internal state.

**In scope (RF coverage from BRD-07 §2):**
- RF-01 partial — terminal handling for `judge_confirmed`, `stopped_by_budget`, `user_cancelled`, `errored`. The three honest stops (`honest_unanswerable`, `honest_contradiction`, `honest_ambiguous`) are wired as enum values but the **policy that selects them** lives in BRD-09.
- RF-06 — question-type classification via the existing `LLMRole.CLASSIFIER`.
- RF-11 — recoverable error path with `AgentErroredEvent`.
- RF-14 — plan critic with hard cap of 2 revisions.
- RF-15 — disconfirmation pass (adversarial re-query) inside `_handle_judging` when judge rejects.

**Non-goals (deferred):**
- Confidence formula `min(S, J)` and the structural component S — BRD-08.
- Layered stopping policy A+D+B+E+F (claim coverage, source agreement, judge, honest, budget) — BRD-09 plugs `StoppingSignal` checks into `_handle_analyzing` / `_handle_judging`.
- SSE transport, `Last-Event-ID` resume, run-worker registry, DB persistence of emitted events — BRD-10.
- Fork & resume — BRD-15.
- Output renderers (prose vs structured) — BRD-16. For V1 the synthesizer always produces prose; the BRD-16 renderer reads `StoppedEvent.answer_prose` later.
- The 5-question calibration eval set — BRD-17.

---

## 2. Architectural Alignment

| Rule (copilot-instructions §3) | Compliance |
|---|---|
| #1 Three plugin seams | The FSM **consumes** the `Source` seam via `app.sources.registry.get_registry()`. It does **not** introduce new seams. |
| #2 Three not-seams (planner / storage / LLM) | The FSM **is** the planner / orchestrator. It calls `app.llm.client.llm.call` directly. No abstraction layer is added. |
| #3 `stop_reason` is an enum | All terminal paths assign one of the 7 `StopReason` values. No free-text. |
| #4 Events are append-only | The orchestrator **emits** events; it never reads back. The callback owner (BRD-10 worker) decides what to persist. |
| #5 Schema evolution = `extra="allow"` | `RunState` uses `ConfigDict(extra="allow")`. All event models already comply (BRD-02). |
| #7 FE↔BE contract | Adding `CritiqueOutput` to `app.llm.models` does **not** affect the event JSON schema; `scripts/export_types.py` does not need to run. |
| #8 `final_confidence = min(S, J)` (RF-12) | Until BRD-08 ships, `structural_confidence` is set to a placeholder = `RunState.coverage_ratio()` and `final_confidence = min(S, J)`. BRD-08 will replace the placeholder with the real weighted score. |
| English-only artifacts (L-001 / language policy) | All code, docstrings, log keys, exception messages in English. The synthesizer prompt remains in English and instructs the LLM to reply in the user's language (already in `app/llm/prompts.py`). |
| `pyright --strict` + `ruff` clean | `from __future__ import annotations`, explicit types, no `Any` leak, no untyped containers. |
| Async-first | Every handler is `async def`. No blocking `time.sleep` / `requests`. The orchestrator never holds a lock; concurrency is the worker's problem (BRD-10). |
| Mandatory unit tests (L-002) | Coder ships ≥ 30 unit tests, target ≥ 90 % coverage on `app/agent/`, mocking LLM and sources. |

---

## 3. Deviations from BRD-07 §4 (binding overrides)

BRD-07 §4 contains structural drift that **must be corrected** in this implementation. Each override below is binding for the Coder.

### O-01. `LLMRole.CRITIC` does not exist — reuse `PLANNER`

BRD-07 §4.5 calls `llm.call(role=LLMRole.CRITIC, ...)`. The enum in [backend/app/llm/roles.py](../../../backend/app/llm/roles.py) defines only `CLASSIFIER | PLANNER | SYNTHESIZER | JUDGE`. Adding a fifth role bleeds BRD-05 work into BRD-07 and forces a new prompt + role config.

**Decision:** the critic step reuses `LLMRole.PLANNER` with a **critique-specific user message** that asks the planner to self-review. The planner's temperature (0.2) is acceptable for critique. No enum change.

If a future BRD wants a dedicated critic, it adds the role then.

### O-02. `CritiqueOutput` model missing — add it to `app.llm.models`

BRD-07 imports `CritiqueOutput` but it does not exist. Add the following Pydantic model to [backend/app/llm/models.py](../../../backend/app/llm/models.py):

```python
class CritiqueOutput(BaseModel):
    """Output of the plan critic step (RF-14)."""

    acceptable: bool = Field(..., description="True if the plan is good enough to execute")
    summary: str = Field(..., description="One-paragraph evaluation")
    issues: list[str] = Field(default_factory=list, description="Concrete problems found")
    suggested_changes: list[str] = Field(
        default_factory=list,
        description="Actionable revisions (only used if acceptable=False)",
    )
```

Re-export from `app/llm/__init__.py`. This is the only intrusion into BRD-05 code and is explicitly authorised by BRD-07 §2 RF-14 coverage.

### O-03. `llm.call` signature mismatch

BRD-07 §4.5 uses `await llm.call(role=..., user_message="...", response_model=...)`. The real signature in [backend/app/llm/client.py](../../../backend/app/llm/client.py) is:

```python
async def call(
    self,
    role: LLMRole,
    messages: list[dict[str, str]],
    response_model: type[T],
) -> T: ...
```

All call sites in this BRD-07 implementation **must** wrap the user message in a single-element list:

```python
result = await llm.call(
    role=LLMRole.PLANNER,
    messages=[{"role": "user", "content": user_prompt}],
    response_model=PlanOutput,
)
```

The client auto-prepends the role system prompt when no `system` message is present (already verified in `_has_system_message`).

### O-04. `_detect_question_type` heuristic violates RF-06

BRD-07 §4.4 detects question type via keyword matching. RF-06 mandates an LLM classifier and the project already ships `LLMRole.CLASSIFIER` + `QuestionClassification` model returning a 1-8 bucket. **Replace** the heuristic with a real LLM call. Mapping:

| `QuestionClassification.question_type` | `QuestionType` (5-value enum) | Behaviour |
|---|---|---|
| 1 | `FACTUAL` | continue |
| 2 | `COMPARATIVE` | continue |
| 3 | `DEFINITIONAL` | continue |
| 4 | `CAUSAL` | continue |
| 5 | (aggregate / SotA-ish) | `STATE_OF_ART` | continue |
| 6, 7, 8 | — | emit `StoppedEvent(stop_reason=HONEST_UNANSWERABLE)` immediately; never enter PLANNING |

This is the **first honest-stop path the orchestrator owns** and is fully in scope for RF-06 + RF-01.

### O-05. `datetime.utcnow()` is deprecated in Python 3.12

Replace `datetime.utcnow` with `datetime.now(UTC)` (or use `time.time()` for monotonic checks). Already required by `pyright --strict` warnings.

### O-06. `RunState` typing modernisation

- Replace every `Optional[X]` with `X | None` (project convention).
- Replace `covered_claims: set[str]` with `list[str]` to remove a Pydantic v2 set-serialisation footgun and to keep the model JSON-safe (it will eventually be persisted as JSONB if anyone snapshots state). Use `if claim_id not in self.covered_claims:` guards for set semantics.
- Same for `uncoverable_claims` and `failed_sources`.
- `draft_sections: list[dict] | None` → `list[AnswerSection] | None` (import from `app.domain.events`).
- `contradictions: list[dict]` → `list[ContradictionDetectedEvent]` (same import).
- Add `model_config = ConfigDict(extra="allow", arbitrary_types_allowed=False)`.

### O-07. `RunState.transition_to` lazy import

BRD-07 does `from app.agent.states import can_transition` inside the method to avoid circular imports. With the file layout below the circular import does not happen — keep the import at module level for `pyright` cleanliness.

### O-08. `_handle_searching` budget gate

BRD-07 increments `search_count` **once per round** but the budget cap (`max_searches = 20`) is interpreted as "20 search rounds". A round can include N tool calls (one per pending claim). Clarify: **budget unit is rounds, not individual tool calls**. Each `_handle_searching` invocation = 1 round = 1 increment. Document this in the `RunState.max_searches` docstring.

### O-09. Judge "max attempts" must not silently confirm

BRD-07 §4.4 final branch: when `judge_attempts >= max_judge_attempts` it calls `_stop(JUDGE_CONFIRMED)` even though the judge said `passed=False`. That is a **false positive** and breaks RF-01's "honest stops are successes" invariant.

**Override:** when `judge_attempts >= max_judge_attempts` and the judge has never approved, stop with `STOPPED_BY_BUDGET` (the run exhausted its judge budget without confirmation). The final answer in `StoppedEvent.answer_prose` is `None`; the last draft stays available on `RunState.draft_answer` for the worker to surface if it wants.

### O-10. Stop-and-emit ordering

`_stop` currently:
1. sets `state.stop_reason`
2. transitions to STOPPED
3. emits `StoppedEvent`

Keep the order but **fold the answer assembly into `_stop`**, not into `_handle_drafting`, so the synthesizer output and citations are attached to the terminal event consistently for `judge_confirmed`. The orchestrator must populate `StoppedEvent.answer_prose` **only** when `stop_reason == JUDGE_CONFIRMED`. For all other reasons leave it `None` (RF-04 honest stop).

### O-11. `EvidenceItem` is internal — keep separate from `EvidenceAddedEvent`

`RunState.evidence: list[EvidenceItem]` and `EvidenceAddedEvent` are two different things. Internal items carry an `event_id` reference (UUID) so that `ClaimCoveredEvent.evidence_ids` can be populated from in-memory state without re-querying the event log. The orchestrator generates a UUID per `EvidenceAddedEvent` it emits (set `event.id = uuid4()`) and stores the same UUID in the matching `EvidenceItem.event_id`. Persistence may rewrite IDs later (BRD-10), but the in-memory consistency is enough to satisfy AC-04.

### O-12. `RunState.total_tokens` tracking is best-effort

The current `LLMClient` does not return token counts (instructor strips them). Increment `total_tokens` via `count_tokens(text)` from `app.llm.client` applied to inputs only. Document in the docstring that this is a lower-bound estimate. Real billing accounting is BRD-17 territory.

### O-13. `_handle_analyzing` decision rule

BRD-07's stub "if `all_claims_resolved()` → DRAFTING else if `search_count < max` → SEARCHING else → DRAFTING" is fine. Add **one** explicit safety net: if `coverage_ratio() == 0.0` **and** `search_count >= 5`, transition to STOPPED with `HONEST_UNANSWERABLE`. This is the orchestrator-level honest stop; BRD-09 will replace it with the layered policy.

### O-14. `_handle_judging` disconfirmation pass (RF-15)

When `judge_event.passed == False` and `judge_attempts < max_judge_attempts`, before going back to SEARCHING:

1. Pick the top-2 issues from `judge_event.suggested_improvements`.
2. For each issue, mark the corresponding claim(s) `pending` again and emit a `ConfidenceMismatchEvent` if `|S - J| > 0.3`.
3. Transition back to `SEARCHING`.

The mapping from "issue text" to "claim id" uses a simple LLM call with `LLMRole.PLANNER` returning a list of claim IDs (reuse `PlanOutput` is overkill — define a small inline structured output called `IssueToClaimMapping` in `app/agent/tasks/draft.py`).

### O-15. Cancellation is checked **before** each handler, not inside

`run()` already does this. Reinforce: every handler must be **idempotent** if cancelled mid-call so that a cancelled draft does not leave partial state. Concretely, no handler may mutate `RunState.draft_answer` until the LLM call returns. The `_cancelled` flag is checked at the top of every loop iteration.

---

## 4. File Layout

Create (or replace empty `__init__.py`):

```
backend/app/agent/
  __init__.py                # re-export AgentOrchestrator, AgentState, RunState
  states.py                  # AgentState enum + TRANSITIONS + can_transition
  run_state.py               # RunState Pydantic model + EvidenceItem
  orchestrator.py            # AgentOrchestrator class
  tasks/
    __init__.py              # re-export task entry points
    plan.py                  # create_plan, critique_plan, revise_plan
    search.py                # execute_search_round
    analyze.py               # analyze_evidence (claim coverage / contradiction)
    draft.py                 # draft_answer, evaluate_with_judge
    classify.py              # classify_question (LLMRole.CLASSIFIER wrapper)

backend/app/llm/
  models.py                  # ADD CritiqueOutput
  __init__.py                # ADD CritiqueOutput to __all__

backend/tests/
  test_agent_states.py            # FSM transitions
  test_agent_run_state.py         # RunState methods
  test_agent_orchestrator.py      # End-to-end with mocked LLM + sources
  test_agent_tasks_plan.py        # create_plan / critique_plan / revise_plan
  test_agent_tasks_classify.py    # classify_question + RF-06 honest stop
  test_agent_tasks_search.py      # execute_search_round with mocked registry
  test_agent_tasks_analyze.py     # analyze_evidence (coverage, contradictions)
  test_agent_tasks_draft.py       # draft_answer + evaluate_with_judge
```

No other directory is touched. **In particular, `app/services/`, `app/routes/`, `app/models/` are not modified** — wiring the orchestrator to a worker / route is BRD-10.

---

## 5. Detailed File Specifications

### 5.1 `backend/app/agent/states.py`

Faithful to BRD-07 §4.2 with `from __future__ import annotations`. The `TRANSITIONS` dict is the **only** authority on legal transitions; `RunState.transition_to` calls `can_transition` for validation.

Add one helper not in the BRD:

```python
TERMINAL_STATES: frozenset[AgentState] = frozenset({AgentState.STOPPED, AgentState.ERRORED})

def is_terminal(state: AgentState) -> bool:
    return state in TERMINAL_STATES
```

### 5.2 `backend/app/agent/run_state.py`

Apply all overrides from O-06 / O-11 / O-12. Final shape:

```python
"""RunState — mutable state for an executing research agent."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.agent.states import AgentState, can_transition
from app.domain.enums import QuestionType, StopReason
from app.domain.events import (
    AnswerSection,
    ContradictionDetectedEvent,
    SubClaim,
)


class EvidenceItem(BaseModel):
    """In-memory evidence linked to an emitted EvidenceAddedEvent."""

    model_config = ConfigDict(extra="allow", frozen=False)

    event_id: UUID = Field(default_factory=uuid4)
    claim_id: str
    source_url: str
    source_title: str
    text: str
    polarity: str  # "supports" | "contradicts" | "neutral"
    confidence: float = Field(ge=0.0, le=1.0)


class RunState(BaseModel):
    """Ephemeral mutable state. Events are the immutable record (RF-03)."""

    model_config = ConfigDict(extra="allow")

    # Identity
    run_id: UUID
    question: str
    user_context: str | None = None
    question_type: QuestionType | None = None

    # Configuration
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    output_format: str = "prose"

    # FSM
    current_state: AgentState = AgentState.INIT
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Planning
    sub_claims: list[SubClaim] = Field(default_factory=list)
    plan_revision_count: int = 0
    max_plan_revisions: int = 2  # RF-14 hard cap

    # Evidence
    evidence: list[EvidenceItem] = Field(default_factory=list)
    covered_claims: list[str] = Field(default_factory=list)
    uncoverable_claims: list[str] = Field(default_factory=list)
    contradictions: list[ContradictionDetectedEvent] = Field(default_factory=list)

    # Search
    search_count: int = 0
    max_searches: int = 20  # rounds, not individual tool calls (O-08)
    failed_sources: list[str] = Field(default_factory=list)

    # Answer
    draft_answer: str | None = None
    draft_sections: list[AnswerSection] | None = None
    draft_citations: list[str] = Field(default_factory=list)

    # Judge
    judge_attempts: int = 0
    max_judge_attempts: int = 3
    last_judge_confidence: float | None = None
    last_structural_confidence: float | None = None

    # Terminal
    stop_reason: StopReason | None = None
    final_answer: str | None = None

    # Metrics
    total_tokens: int = 0
    iteration_count: int = 0

    def transition_to(self, new_state: AgentState) -> None:
        if not can_transition(self.current_state, new_state):
            raise ValueError(
                f"Invalid transition: {self.current_state} -> {new_state}"
            )
        self.current_state = new_state

    def add_evidence(self, item: EvidenceItem) -> None:
        self.evidence.append(item)

    def mark_claim_covered(self, claim_id: str) -> None:
        if claim_id not in self.covered_claims:
            self.covered_claims.append(claim_id)
        for c in self.sub_claims:
            if c.id == claim_id:
                c.status = "covered"

    def mark_claim_uncoverable(self, claim_id: str) -> None:
        if claim_id not in self.uncoverable_claims:
            self.uncoverable_claims.append(claim_id)
        for c in self.sub_claims:
            if c.id == claim_id:
                c.status = "uncoverable"

    def pending_claims(self) -> list[SubClaim]:
        return [c for c in self.sub_claims if c.status == "pending"]

    def all_claims_resolved(self) -> bool:
        return not self.pending_claims()

    def coverage_ratio(self) -> float:
        if not self.sub_claims:
            return 0.0
        return len(self.covered_claims) / len(self.sub_claims)
```

### 5.3 `backend/app/agent/tasks/classify.py`

```python
"""RF-06 question classifier wrapper."""

from __future__ import annotations

from app.domain.enums import QuestionType
from app.llm import LLMRole, QuestionClassification, llm

# 1-8 → 5-value enum (or None to signal honest_unanswerable)
_BUCKET_MAP: dict[int, QuestionType] = {
    1: QuestionType.FACTUAL,
    2: QuestionType.COMPARATIVE,
    3: QuestionType.DEFINITIONAL,
    4: QuestionType.CAUSAL,
    5: QuestionType.STATE_OF_ART,
}


async def classify_question(question: str) -> tuple[QuestionType | None, QuestionClassification]:
    """Return (mapped_type, raw_verdict).

    ``mapped_type is None`` means the LLM marked the question unanswerable
    (buckets 6/7/8) and the orchestrator must emit ``honest_unanswerable``.
    """
    verdict = await llm.call(
        role=LLMRole.CLASSIFIER,
        messages=[{"role": "user", "content": question}],
        response_model=QuestionClassification,
    )
    if not verdict.answerable or verdict.question_type not in _BUCKET_MAP:
        return None, verdict
    return _BUCKET_MAP[verdict.question_type], verdict
```

### 5.4 `backend/app/agent/tasks/plan.py`

Faithful to BRD-07 §4.5 with overrides O-01 / O-02 / O-03 applied:

- `create_plan(question)` calls `LLMRole.PLANNER` with `PlanOutput`.
- `critique_plan(question, sub_claims)` calls `LLMRole.PLANNER` with `CritiqueOutput` and a user-message template:
  ```
  You are now evaluating a research plan you previously drafted.
  Original question: {question}
  Current sub-claims:
  - c1: ...
  - c2: ...
  Identify issues, suggest changes, and decide whether to accept.
  ```
- `revise_plan(question, current_claims, attempt_number)` calls `LLMRole.PLANNER` with `PlanOutput` and includes the rejected claims in the user message.

Each function returns the **corresponding event** (`PlanCreatedEvent`, `PlanCritiquedEvent`, `PlanRevisedEvent`). The orchestrator emits them.

### 5.5 `backend/app/agent/tasks/search.py`

```python
"""Execute one search round across pending claims."""

from __future__ import annotations

from uuid import uuid4

from app.agent.run_state import EvidenceItem, RunState
from app.domain.enums import EvidencePolarity, SourceType
from app.domain.events import (
    BaseEvent,
    EvidenceAddedEvent,
    SourceFailedEvent,
    ToolCalledEvent,
)
from app.seams.source import SourceError
from app.sources.registry import get_registry


async def execute_search_round(state: RunState) -> list[BaseEvent]:
    """Issue one search per pending claim, cascading through sources.

    Cascade order: Tavily first, Wikipedia on SourceFailed.
    Emits ToolCalled + (EvidenceAdded | SourceFailed).
    """
    registry = get_registry()
    events: list[BaseEvent] = []

    for claim in state.pending_claims()[:5]:  # cap fan-out per round
        query = claim.text
        order: list[SourceType] = [SourceType.TAVILY, SourceType.WIKIPEDIA]

        for source_type in order:
            if source_type not in registry.types():
                continue
            events.append(
                ToolCalledEvent(
                    source_type=source_type,
                    query=query,
                    query_intent=f"Verify {claim.id}: {claim.text[:80]}",
                    target_claim_id=claim.id,
                )
            )
            try:
                results = await registry.get(source_type).search(query, max_results=3)
            except SourceError as exc:
                events.append(
                    SourceFailedEvent(
                        source_type=source_type,
                        query=query,
                        error_message=exc.message,
                        recoverable=exc.recoverable,
                    )
                )
                state.failed_sources.append(f"{source_type.value}:{query}")
                continue

            for r in results:
                ev = EvidenceAddedEvent(
                    id=uuid4(),
                    source_type=source_type,
                    source_url=r.url,
                    source_title=r.title,
                    extracted_text=(r.snippet or "")[:1000],
                    polarity=EvidencePolarity.NEUTRAL,  # analyzer refines this
                    target_claim_id=claim.id,
                    confidence=r.relevance_score or 0.5,
                )
                events.append(ev)
                assert ev.id is not None
                state.add_evidence(
                    EvidenceItem(
                        event_id=ev.id,
                        claim_id=claim.id,
                        source_url=r.url,
                        source_title=r.title,
                        text=ev.extracted_text,
                        polarity=ev.polarity.value,
                        confidence=ev.confidence,
                    )
                )
            break  # got results from this source, skip the cascade

    return events
```

**Notes for Coder:**
- Cap of 5 claims per round is a deliberate scope limit; documented in the docstring.
- Polarity is set to `NEUTRAL` at search time; the analyser step refines it (BRD-08 will replace this with an LLM polarity classifier).
- `SourceError` is the only exception type expected from sources (BRD-06 contract); anything else propagates and is caught by `AgentOrchestrator.run()` → `AgentErroredEvent`.

### 5.6 `backend/app/agent/tasks/analyze.py`

```python
"""Analyse collected evidence: mark coverage, detect contradictions."""

from __future__ import annotations

from app.agent.run_state import RunState
from app.domain.events import (
    BaseEvent,
    ClaimCoveredEvent,
    ClaimUncoverableEvent,
)


COVERAGE_MIN_EVIDENCE = 2
COVERAGE_MIN_AVG_CONFIDENCE = 0.4


async def analyze_evidence(state: RunState) -> list[BaseEvent]:
    """Decide which pending claims are covered or uncoverable.

    V1 heuristic (BRD-08 will replace with the layered policy):
      - claim covered when ≥2 supporting evidence with avg confidence ≥0.4
      - claim uncoverable when ≥2 search rounds passed without any evidence
    """
    events: list[BaseEvent] = []

    for claim in list(state.pending_claims()):
        claim_evidence = [e for e in state.evidence if e.claim_id == claim.id]

        if len(claim_evidence) >= COVERAGE_MIN_EVIDENCE:
            avg_conf = sum(e.confidence for e in claim_evidence) / len(claim_evidence)
            if avg_conf >= COVERAGE_MIN_AVG_CONFIDENCE:
                state.mark_claim_covered(claim.id)
                events.append(
                    ClaimCoveredEvent(
                        claim_id=claim.id,
                        claim_text=claim.text,
                        evidence_ids=[e.event_id for e in claim_evidence],
                        coverage_rationale=(
                            f"{len(claim_evidence)} sources, "
                            f"avg confidence {avg_conf:.2f}"
                        ),
                    )
                )
                continue

        # No evidence after multiple rounds → uncoverable
        if not claim_evidence and state.search_count >= 2:
            state.mark_claim_uncoverable(claim.id)
            events.append(
                ClaimUncoverableEvent(
                    claim_id=claim.id,
                    claim_text=claim.text,
                    reason="No relevant evidence found after 2 search rounds",
                    attempted_sources=[],  # BRD-09 fills cascade history
                )
            )

    return events
```

### 5.7 `backend/app/agent/tasks/draft.py`

Owns three functions:

```python
async def draft_answer(state: RunState) -> SynthesizedAnswer: ...
async def evaluate_with_judge(state: RunState) -> JudgeRuledEvent: ...
async def map_issues_to_claims(  # RF-15 disconfirmation helper
    issues: list[str], sub_claims: list[SubClaim]
) -> list[str]: ...
```

Implementation notes (Coder fills the prompts):

- `draft_answer` calls `LLMRole.SYNTHESIZER` with `SynthesizedAnswer` and a user message containing the question, the user context (if any), all covered evidence as a bullet list with URLs. Stores `result.prose`, `result.citations`, and structures `result.key_points` into `AnswerSection` objects.
- `evaluate_with_judge` calls `LLMRole.JUDGE` with `JudgeVerdict`. Constructs `JudgeRuledEvent` with:
  - `judge_model = ROLE_CONFIGS[LLMRole.JUDGE].model`
  - `judge_confidence = verdict.confidence`
  - `structural_confidence = state.coverage_ratio()`  # placeholder until BRD-08
  - `final_confidence = min(judge_confidence, structural_confidence)`
  - `threshold = state.confidence_threshold`
  - `passed = final_confidence >= threshold and verdict.verdict == "approve"`
  - `suggested_improvements = verdict.improvements`
- `map_issues_to_claims` defines a small inline `IssueToClaimMapping(BaseModel)` with `claim_ids: list[str]`, calls `LLMRole.PLANNER` with both the issue list and the claim list, returns the claim IDs to re-open.

### 5.8 `backend/app/agent/orchestrator.py`

Faithful to BRD-07 §4.4 with all overrides applied. The most important diffs:

```python
# Replace __init__ default datetime
from datetime import UTC, datetime

# Replace QuestionAskedEvent emission
await self.emit(QuestionAskedEvent(
    question=self.state.question,
    user_context=self.state.user_context,
    detected_question_type=None,  # populated after classification
))

# RF-06 honest-stop branch
async def _detect_question_type(self) -> bool:
    """Return True to continue, False if stopped honestly."""
    mapped, raw = await classify_question(self.state.question)
    if mapped is None:
        await self._stop(StopReason.HONEST_UNANSWERABLE)
        return False
    self.state.question_type = mapped
    return True

# In run() — after QuestionAskedEvent
if not await self._detect_question_type():
    return StopReason.HONEST_UNANSWERABLE

# _handle_critiquing — pass question into critique_plan
critique = await critique_plan(self.state.question, self.state.sub_claims)

# _handle_judging — apply O-09 + O-14
async def _handle_judging(self) -> None:
    judge_event = await evaluate_with_judge(self.state)
    await self.emit(judge_event)
    self.state.last_judge_confidence = judge_event.judge_confidence
    self.state.last_structural_confidence = judge_event.structural_confidence
    self.state.judge_attempts += 1

    if judge_event.passed:
        await self._stop(StopReason.JUDGE_CONFIRMED)
        return

    if self.state.judge_attempts >= self.state.max_judge_attempts:
        await self._stop(StopReason.STOPPED_BY_BUDGET)  # O-09
        return

    # RF-15 disconfirmation pass (O-14)
    divergence = abs(
        judge_event.structural_confidence - judge_event.judge_confidence
    )
    if divergence > 0.3:
        await self.emit(
            ConfidenceMismatchEvent(
                structural_confidence=judge_event.structural_confidence,
                judge_confidence=judge_event.judge_confidence,
                divergence=divergence,
                trust_flag="structural/judge divergence > 0.3",
            )
        )

    issues = judge_event.suggested_improvements or []
    if issues:
        claim_ids = await map_issues_to_claims(issues[:2], self.state.sub_claims)
        for cid in claim_ids:
            for c in self.state.sub_claims:
                if c.id == cid and c.status == "covered":
                    c.status = "pending"
                    if cid in self.state.covered_claims:
                        self.state.covered_claims.remove(cid)

    self.state.transition_to(AgentState.SEARCHING)

# _stop — populate answer
async def _stop(self, reason: StopReason) -> StopReason:
    self.state.stop_reason = reason
    self.state.transition_to(AgentState.STOPPED)
    answer = self.state.draft_answer if reason == StopReason.JUDGE_CONFIRMED else None
    await self.emit(StoppedEvent(
        stop_reason=reason,
        answer_prose=answer,
        total_tokens=self.state.total_tokens,
    ))
    logger.info(
        "agent_run_complete",
        run_id=str(self.state.run_id),
        stop_reason=reason.value,
        iterations=self.state.iteration_count,
    )
    return reason
```

The main `run()` loop is otherwise as in BRD-07 §4.4. The `match` statement on `current_state` stays.

### 5.9 `backend/app/agent/__init__.py`

```python
"""Agent FSM package — research loop orchestrator."""

from __future__ import annotations

from app.agent.orchestrator import AgentOrchestrator, EventCallback
from app.agent.run_state import EvidenceItem, RunState
from app.agent.states import AgentState, TERMINAL_STATES, can_transition, is_terminal

__all__ = (
    "AgentOrchestrator",
    "AgentState",
    "EventCallback",
    "EvidenceItem",
    "RunState",
    "TERMINAL_STATES",
    "can_transition",
    "is_terminal",
)
```

### 5.10 `backend/app/agent/tasks/__init__.py`

```python
from __future__ import annotations

from app.agent.tasks.analyze import analyze_evidence
from app.agent.tasks.classify import classify_question
from app.agent.tasks.draft import draft_answer, evaluate_with_judge, map_issues_to_claims
from app.agent.tasks.plan import create_plan, critique_plan, revise_plan
from app.agent.tasks.search import execute_search_round

__all__ = (
    "analyze_evidence",
    "classify_question",
    "create_plan",
    "critique_plan",
    "draft_answer",
    "evaluate_with_judge",
    "execute_search_round",
    "map_issues_to_claims",
    "revise_plan",
)
```

---

## 6. Task Breakdown for Coder

Each task is one logical unit. Effort estimates are advisory.

| # | Task | Files touched | Effort |
|---|------|---------------|--------|
| 1 | Add `CritiqueOutput` to `app/llm/models.py` and re-export | `app/llm/models.py`, `app/llm/__init__.py` | XS |
| 2 | `app/agent/states.py` — enum + transitions + helpers | new | S |
| 3 | `app/agent/run_state.py` — RunState + EvidenceItem | new | M |
| 4 | `app/agent/tasks/classify.py` — RF-06 wrapper | new | S |
| 5 | `app/agent/tasks/plan.py` — create/critique/revise | new | M |
| 6 | `app/agent/tasks/search.py` — search round | new | M |
| 7 | `app/agent/tasks/analyze.py` — coverage heuristic | new | S |
| 8 | `app/agent/tasks/draft.py` — draft + judge + issue mapping | new | M |
| 9 | `app/agent/orchestrator.py` — full FSM with overrides | new | L |
| 10 | `app/agent/__init__.py` + `app/agent/tasks/__init__.py` | new | XS |
| 11 | Unit tests (8 files, ≥30 tests) | new under `tests/` | L |
| 12 | Run full backend suite + `pyright --strict` + `ruff` | — | S |

**Strict ordering: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12.** Step 9 depends on every prior task.

---

## 7. Testing Strategy

All tests use **mocked LLM client** (monkeypatch `app.llm.client.client.chat.completions.create`) and **mocked source registry** (`monkeypatch.setattr("app.sources.registry._registry", FakeRegistry(...))` after constructing a fake). No real network calls. No DB.

### 7.1 `test_agent_states.py`
- `can_transition` returns `True` for every edge in `TRANSITIONS`.
- `can_transition(INIT, SEARCHING) is False` (must go through PLANNING).
- `is_terminal(STOPPED) is True`, `is_terminal(PLANNING) is False`.
- `TRANSITIONS[STOPPED] == set()`.

### 7.2 `test_agent_run_state.py`
- `transition_to(legal)` succeeds; `transition_to(illegal)` raises `ValueError`.
- `mark_claim_covered` flips the matching `SubClaim.status` and dedupes.
- `mark_claim_uncoverable` likewise.
- `pending_claims` filters correctly.
- `all_claims_resolved()` True/False matrix.
- `coverage_ratio()` for 0 / partial / full.
- Pydantic serialisation round-trip via `model_dump_json` (catches non-JSON-safe types — protects O-06).

### 7.3 `test_agent_tasks_classify.py`
- Each bucket 1-5 maps to the right `QuestionType`.
- Buckets 6/7/8 → `(None, verdict)`.
- `answerable=False` → `(None, verdict)` regardless of bucket.

### 7.4 `test_agent_tasks_plan.py`
- `create_plan` returns a `PlanCreatedEvent` with `sub_claims` matching the LLM stub.
- `critique_plan(acceptable=True)` and `(acceptable=False, with issues)`.
- `revise_plan` increments `attempt_number` and preserves `previous_sub_claims`.

### 7.5 `test_agent_tasks_search.py`
- One pending claim, Tavily returns 3 results → 1 `ToolCalled` + 3 `EvidenceAdded`.
- Tavily raises `SourceError` → 1 `ToolCalled` + 1 `SourceFailed` + cascade to Wikipedia (1 more `ToolCalled` + N `EvidenceAdded`).
- Both sources fail → state has 2 entries in `failed_sources` and no evidence.
- Cap at 5 claims per round (give 7, expect 5 processed).

### 7.6 `test_agent_tasks_analyze.py`
- 2 evidence items with avg conf 0.5 → `ClaimCovered`.
- 1 evidence item → no `ClaimCovered`.
- 0 evidence after `search_count=2` → `ClaimUncoverable`.

### 7.7 `test_agent_tasks_draft.py`
- `draft_answer` populates `state.draft_answer`, `state.draft_citations`.
- `evaluate_with_judge` builds `JudgeRuledEvent` with `final_confidence = min(S, J)` and `passed` matching the threshold logic.
- `map_issues_to_claims` returns the expected claim IDs.

### 7.8 `test_agent_orchestrator.py` (most important)

Use an `EventCollector` callback that appends every emitted event to a list. Mock all LLM roles and the source registry. Key scenarios:

| Test | Scenario | Expected stop_reason | Expected event types in order |
|------|----------|----------------------|-------------------------------|
| `test_run_happy_path` | Classifier → answerable, plan accepted, evidence covers all claims, judge approves | `JUDGE_CONFIRMED` | QuestionAsked, PlanCreated, PlanCritiqued, ToolCalled+, EvidenceAdded+, ClaimCovered+, JudgeRuled, Stopped |
| `test_rf06_unanswerable` | Classifier returns bucket 6 | `HONEST_UNANSWERABLE` | QuestionAsked, Stopped |
| `test_rf14_max_revisions` | Critic rejects twice, then accepts | continues to SEARCHING after 2 revisions | PlanCritiqued, PlanRevised, PlanCritiqued, PlanRevised, PlanCritiqued, ToolCalled… |
| `test_budget_exhausted` | `max_searches=2`, no claim ever covered | `STOPPED_BY_BUDGET` | ... 2 search rounds ... Stopped |
| `test_cancel_mid_loop` | Call `orchestrator.cancel()` after `QuestionAsked` | `USER_CANCELLED` | QuestionAsked, Stopped |
| `test_judge_max_attempts` | Judge rejects 3 times in a row | `STOPPED_BY_BUDGET` (O-09 — never silent approve) | ..., JudgeRuled×3, Stopped |
| `test_rf15_disconfirmation` | Judge rejects with issues, |S-J|>0.3 | continues | JudgeRuled, ConfidenceMismatch, ToolCalled… |
| `test_error_path` | Source raises non-SourceError exception | `ERRORED` | ..., AgentErrored, Stopped |
| `test_illegal_transition_raises` | Call `state.transition_to(STOPPED)` from INIT directly | `ValueError` | — |
| `test_evidence_ids_in_claim_covered` | Coverage rationale's `evidence_ids` match the in-memory `EvidenceItem.event_id` set (O-11) | — | — |

### 7.9 Coverage target

`pytest --cov=app/agent --cov-fail-under=90`. Anything in `app/agent/` below 90 % is a Major review finding.

### 7.10 What is **not** tested here

- Real LLM round-trips (integration suite, BRD-17).
- Real Tavily/Wikipedia calls (covered by BRD-06 tests).
- DB persistence of events (BRD-10).
- SSE serialisation (BRD-10).
- Calibration accuracy on the 5-question eval set (BRD-17).

---

## 8. Acceptance Criteria Mapping

| AC (BRD-07 §5) | Verified by |
|---|---|
| AC-01 FSM follows valid transitions | `test_agent_states.py` + `test_run_happy_path` |
| AC-02 Plan critic max 2 revisions | `test_rf14_max_revisions` |
| AC-03 Search budget enforced | `test_budget_exhausted` |
| AC-04 Judge approval stops run | `test_run_happy_path` + `test_evidence_ids_in_claim_covered` |
| AC-05 Cancellation works | `test_cancel_mid_loop` |

Plus IP-07-only acceptance:

- **AC-06 (O-04):** RF-06 unanswerable buckets → `HONEST_UNANSWERABLE` stop. Verified by `test_rf06_unanswerable`.
- **AC-07 (O-09):** Judge max attempts never produces a silent `JUDGE_CONFIRMED`. Verified by `test_judge_max_attempts`.
- **AC-08 (O-14):** RF-15 disconfirmation re-opens claims and emits `ConfidenceMismatchEvent` when divergence > 0.3. Verified by `test_rf15_disconfirmation`.
- **AC-09 (O-11):** `ClaimCoveredEvent.evidence_ids` match `EvidenceItem.event_id` set. Verified by `test_evidence_ids_in_claim_covered`.

---

## 9. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Pyright complains about `instructor`-typed LLM stubs in tests | Med | Low | Use `pyright: ignore[...]` only on test files, never in `app/agent/`. |
| FSM enters infinite loop if judge always rejects and budget never trips | Med | High | O-09 + judge_attempts hard cap. Verified by `test_judge_max_attempts`. |
| Pydantic v2 serialisation breaks for `set[str]` / `datetime` in `RunState` | Low | Med | O-06 replaces sets with lists; `datetime.now(UTC)` is JSON-safe via Pydantic. Round-trip test in `test_agent_run_state.py`. |
| Adding `CritiqueOutput` to `app/llm/__init__.py` triggers BRD-05 review noise | Low | Low | Single additive export, no breaking change; mention explicitly in the PR description. |
| Heuristic in `analyze_evidence` produces silly coverage on real LLM output | Med | Med | This is a known V1 placeholder; BRD-08 replaces it. Test only the structural behaviour, not the heuristic's "accuracy". |
| Wikipedia is the only registered source in CI (no Tavily key) → search cascade tests degrade | Low | Low | Mock `get_registry()` in tests. CI does not call real sources. |

---

## 10. Out of Scope (re-stated, for the reviewer)

- BRD-08 — confidence formula (structural_confidence placeholder = `coverage_ratio()` until then).
- BRD-09 — layered stopping policy (only `judge_confirmed`, `stopped_by_budget`, `user_cancelled`, `errored` and a single `honest_unanswerable` from RF-06 are wired here).
- BRD-10 — SSE, event persistence, run-worker registry, `Last-Event-ID` resume.
- BRD-11..16 — frontend changes.
- BRD-15 — fork and resume.
- BRD-17 — calibration eval.
- Real network calls to Tavily / Wikipedia / GitHub Models in unit tests.

---

## 11. Coder Hand-Off

The Coder agent must:

1. Read this plan **and** BRD-07 in full.
2. Follow the strict task ordering in §6.
3. Apply every override in §3 (they are binding, not advisory).
4. Ship the test matrix in §7. Coverage gate ≥ 90 % on `app/agent/`.
5. Run before declaring done:
   ```powershell
   cd backend
   uv run ruff check app/agent tests
   uv run ruff format --check app/agent tests
   uv run pyright app/agent
   uv run pytest -p no:postgresql -q --cov=app/agent --cov-fail-under=90
   ```
6. Commit message convention: `feat(agent): BRD-07 FSM + research loop (IP-07)`.

Reviewer will score against §8 (AC mapping) and §3 (every override addressed).
