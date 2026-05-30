"""Drafting, judging and disconfirmation helpers.

- ``draft_answer`` calls the synthesizer to produce the final prose.
  WP-2: derives ambiguity_flag (G3), calls select_answer_kind, enforces
  contradiction surfacing (G10), and validates kind-specific payloads.
- ``evaluate_with_judge`` calls the judge and builds ``JudgeRuledEvent``
  with ``final_confidence = min(S, J)`` (O-08 in BRD-07; placeholder S
  until BRD-08 ships). WP-5: includes emit_event callback for degradation.
- ``map_issues_to_claims`` is the RF-15 disconfirmation helper that
  finds which claims to re-open from judge issues.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.agent.run_state import RunState
from app.agent.tasks.select_answer_kind import AnswerKindInputs, select_answer_kind
from app.confidence import calculate_structural_confidence
from app.domain.enums import AnswerKind, EventType
from app.domain.events import (
    AnswerSection,
    JudgeRuledEvent,
    SubClaim,
)
from app.exceptions import LLMContractError
from app.llm import (
    ROLE_CONFIGS,
    JudgeVerdict,
    LLMRole,
    SynthesizedAnswer,
    llm,
)
from app.llm.client import active_judge_model
from app.llm.prompts import build_synthesizer_prompt


class IssueToClaimMapping(BaseModel):
    """Inline structured output for the disconfirmation mapping step."""

    claim_ids: list[str] = Field(default_factory=list)


class _RawSynthesizerPayload(BaseModel):
    # instructor >= 1.x rejects ``dict`` as response_model; this permissive
    # wrapper captures arbitrary keys so the caller can run a second-pass
    # ``SynthesizedAnswer.model_validate`` with a validation context.
    model_config = {"extra": "allow"}


_LIST_OF_STR_FIELDS = (
    "key_points",
    "citations",
    "gaps",
    "contradictions",
    "remaining_uncertainties",
    "redirect_alternatives",
    "alternative_interpretations",
)


def _coerce_to_string(value: Any) -> str:
    """Best-effort coercion of a non-string LLM output into a string."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        # Prefer common text-bearing keys; fall back to joining string values.
        for key in ("text", "content", "summary", "point", "value", "description"):
            v = value.get(key)
            if isinstance(v, str) and v.strip():
                return v
        parts = [v for v in value.values() if isinstance(v, str) and v.strip()]
        if parts:
            return " — ".join(parts)
    if isinstance(value, list):
        return " ".join(_coerce_to_string(v) for v in value if v is not None)
    return str(value) if value is not None else ""


def _coerce_synthesizer_payload(payload: Any) -> Any:
    """Coerce common synthesizer-output type mistakes into the expected shape.

    LLMs frequently emit ``citations=None``, ``remaining_uncertainties="..."``
    (string instead of list), or ``key_points=[{"text": "..."}]`` (dict items).
    Normalising before ``SynthesizedAnswer.model_validate`` avoids errored runs.
    """
    if not isinstance(payload, dict):
        return payload
    for field in _LIST_OF_STR_FIELDS:
        if field not in payload:
            continue
        v = payload[field]
        if v is None:
            payload[field] = []
        elif isinstance(v, str):
            payload[field] = [v] if v.strip() else []
        elif isinstance(v, list):
            payload[field] = [_coerce_to_string(item) for item in v if item is not None]
        else:
            payload[field] = [_coerce_to_string(v)]
    return payload


def _format_evidence_for_claim(state: RunState, claim: SubClaim) -> str:
    items = [e for e in state.evidence if e.claim_id == claim.id]
    if not items:
        return "  (no evidence collected)"
    return "\n".join(f"  - [{e.source_title}]({e.source_url}) — {e.text[:200]}" for e in items)


async def draft_answer(state: RunState) -> SynthesizedAnswer:
    """Synthesize the final answer using all collected evidence.

    WP-2 implementation:
    - G3: derive ambiguity_flag from state.has_event(EventType.AMBIGUITY_DETECTED)
    - Select answer_kind based on question_type, S, coverage, agreement, ambiguity
    - G10: enforce contradictions field when ContradictionDetectedEvent exists
    - Build prompt with answer_kind-specific template
    - Validate and retry on kind mismatch or missing contradictions (once each)
    """
    if state.question_type is None:
        raise ValueError("draft_answer called before question_type was set")

    # G3: derive ambiguity_flag from events
    ambiguity_flag = state.has_event(EventType.AMBIGUITY_DETECTED)

    # G10: check if contradictions are required
    requires_contradictions = state.has_event(EventType.CONTRADICTION_DETECTED)

    # Compute structural confidence inputs
    struct_conf = calculate_structural_confidence(state)
    coverage = state.coverage_ratio()
    # agreement is in struct_conf.score (placeholder — BRD-08 has the real formula)
    # For now, use a heuristic: if no contradictions, agreement = 0.8, else 0.5
    agreement = 0.5 if requires_contradictions else 0.8

    # Select answer kind
    inputs = AnswerKindInputs(
        question_type=state.question_type,
        structural_confidence=struct_conf.score,
        coverage=coverage,
        agreement=agreement,
        ambiguity_flag=ambiguity_flag,
    )
    answer_kind = select_answer_kind(inputs)
    state.selected_answer_kind = answer_kind

    # Format evidence for synthesizer
    evidence_list = [
        {
            "url": e.source_url,
            "title": e.source_title,
            "snippet": e.text,
        }
        for e in state.evidence
    ]

    # IP-25 Phase D: Format hypotheses if present
    hypotheses_list = None
    if state.hypotheses:
        hypotheses_list = [
            {"text": h.text, "priority": h.priority}
            for h in state.hypotheses
        ]

    # Build prompt
    system_prompt, max_tokens = build_synthesizer_prompt(
        question=state.question,
        evidence=evidence_list,
        answer_kind=answer_kind,
        user_language=state.language,
        requires_contradictions=requires_contradictions,
        hypotheses=hypotheses_list,
    )

    # Call synthesizer with retry logic
    retry_count = 0
    max_retries = 1

    while retry_count <= max_retries:
        try:
            raw_payload = await llm.call(
                role=LLMRole.SYNTHESIZER,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": state.question},
                ],
                response_model=_RawSynthesizerPayload,
                max_tokens=max_tokens,
            )

            # Validate with context
            payload_dict = (
                raw_payload.model_dump()
                if hasattr(raw_payload, "model_dump")
                else raw_payload
            )
            payload_dict = _coerce_synthesizer_payload(payload_dict)
            result = SynthesizedAnswer.model_validate(
                payload_dict,
                context={"_requires_contradictions": requires_contradictions},
            )

            # Check kind matches (only when LLM explicitly set answer_kind;
            # None means "not echoed" and the resolver is authoritative).
            if result.answer_kind is not None and result.answer_kind != answer_kind:
                if retry_count == 0:
                    # First mismatch: retry with hardened prefix
                    system_prompt = (
                        f"CRITICAL: You MUST set answer_kind to '{answer_kind.value}'. "
                        f"Any other value will be rejected.\n\n"
                        + system_prompt
                    )
                    retry_count += 1
                    continue
                else:
                    raise LLMContractError(
                        f"Synthesizer returned answer_kind={result.answer_kind.value} "
                        f"after retry; expected {answer_kind.value}"
                    )

            # Stamp the resolver-chosen kind on the result so downstream consumers see it.
            if result.answer_kind is None:
                result.answer_kind = answer_kind

            # Success — populate state and return
            state.draft_answer = result.prose
            state.draft_payload = result
            state.draft_citations = list(result.citations)
            state.draft_sections = [
                AnswerSection(heading=str(idx + 1), content=kp)
                for idx, kp in enumerate(result.key_points)
            ]
            return result

        except ValidationError as exc:
            err_text = str(exc)
            # Check if it's the contradictions requirement violation
            if requires_contradictions and "contradictions required" in err_text:
                if retry_count == 0:
                    system_prompt = (
                        "CRITICAL: The run has detected contradictions. You MUST populate "
                        "the 'contradictions' field with at least one entry. Omitting it "
                        "will cause validation failure.\n\n"
                        + system_prompt
                    )
                    retry_count += 1
                    continue
                else:
                    raise LLMContractError(
                        "Synthesizer omitted contradictions field after retry"
                    ) from exc
            # Kind-shape mismatch: payload claims kind X but populates fields of kind Y
            if "answer_kind" in err_text or "must be populated" in err_text or "must be None" in err_text:
                if retry_count == 0:
                    system_prompt = (
                        f"CRITICAL: You MUST set answer_kind to '{answer_kind.value}' "
                        f"AND populate ONLY the matching kind-specific field. "
                        f"Any other value will be rejected.\n\n"
                        + system_prompt
                    )
                    retry_count += 1
                    continue
                else:
                    raise LLMContractError(
                        f"Synthesizer returned invalid kind shape after retry; expected {answer_kind.value}"
                    ) from exc
            # Other validation error — retry once with hardened prompt; coercion
            # already handled the common type mistakes, so a remaining error
            # likely means the LLM omitted a required field or violated a
            # constraint we cannot auto-fix.
            if retry_count == 0:
                system_prompt = (
                    "CRITICAL: Your previous response failed schema validation. "
                    "Respond with valid JSON matching the schema EXACTLY. "
                    "All list fields must be arrays of strings (never null, never "
                    "a single string, never objects). Required fields must be "
                    "present.\n\n"
                    + system_prompt
                )
                retry_count += 1
                continue
            raise

    # Should not reach here
    raise LLMContractError("Draft answer retry loop exhausted without success")


async def evaluate_with_judge(
    state: RunState,
    emit_event: Any = None,  # WP-5: optional callback for JudgeProviderDegradedEvent
) -> JudgeRuledEvent:
    """Call the judge and assemble a ``JudgeRuledEvent`` (WP-5 extensions).

    WP-4: Includes evidence_saturation (state.last_novelty) in the judge context.
    WP-5: Merges judge.contradictions_detected into final event.
    """
    draft = state.draft_answer or ""
    threshold = state.confidence_threshold

    # WP-4: Include evidence saturation in judge context
    saturation_note = ""
    if state.last_novelty is not None:
        saturation_note = f"\n\nEvidence saturation (novelty): {state.last_novelty:.3f} (lower = more repetitive)"

    # PR-8: surface the evidence corpus to the judge. Without this block the
    # judge sees only `question + draft` and routinely rejects with rationales
    # like "no actual source details are provided to verify these figures".
    # We pass up to 20 items (title, url, polarity, confidence + truncated
    # snippet) prioritising the highest-confidence pieces.
    evidence_block = ""
    if state.evidence:
        top_evidence = sorted(
            state.evidence, key=lambda e: e.confidence, reverse=True
        )[:20]
        lines: list[str] = []
        for idx, item in enumerate(top_evidence, start=1):
            snippet = (item.text or "").strip().replace("\n", " ")
            if len(snippet) > 500:
                snippet = snippet[:500] + "…"
            lines.append(
                f"[{idx}] claim={item.claim_id} polarity={item.polarity} "
                f"conf={item.confidence:.2f}\n"
                f"    title: {item.source_title}\n"
                f"    url: {item.source_url}\n"
                f"    snippet: {snippet}"
            )
        evidence_block = (
            "\n\nEvidence collected during the run "
            f"(top {len(top_evidence)} of {len(state.evidence)} by confidence):\n"
            + "\n".join(lines)
        )

    # C2: the run's confidence threshold is the single gate. The judge
    # applies it internally when deciding verdict=approve|reject. The
    # stopping signal no longer re-checks min(S,J) >= threshold.
    # IP-36: relax "complete" wording — completeness should be judged
    # relative to evidence collected, not against an idealised plan.
    # Otherwise the judge rejects every partial-coverage standard-lane
    # answer and the run dies on STOPPED_BY_BUDGET.
    threshold_rule = (
        f"\n\nConfidence threshold for this run: {threshold:.2f}.\n"
        f"Return verdict=\"approve\" when your confidence is >= {threshold:.2f} "
        f"AND the answer is factually sound and well-grounded in the cited "
        f"evidence. Completeness is judged relative to the evidence actually "
        f"collected: if the answer honestly states its scope and the cited "
        f"evidence supports the claims made, approve even if the plan was "
        f"only partially covered. Reserve verdict=\"reject\" for answers "
        f"that contradict the evidence, fabricate citations, or omit a "
        f"directly-cited finding that would flip the verdict."
    )

    user_msg = (
        f"Question: {state.question}\n\n"
        f"Draft answer:\n{draft}"
        f"{evidence_block}\n\n"
        f"Evaluate factuality, completeness and grounding.{saturation_note}{threshold_rule}"
    )
    verdict = await llm.call(
        role=LLMRole.JUDGE,
        messages=[{"role": "user", "content": user_msg}],
        response_model=JudgeVerdict,
        emit_event=emit_event,  # WP-5: pass through for fallback event
    )
    judge_confidence = verdict.confidence
    structural_confidence = calculate_structural_confidence(state).score
    final_confidence = min(judge_confidence, structural_confidence)
    # C2: threshold is enforced inside the judge LLM (see threshold_rule
    # above); the verdict alone is the gate here. final_confidence stays
    # as a logged metric so the UI can still surface it.
    passed = verdict.verdict.lower() == "approve"

    # WP-5: Merge judge.contradictions_detected into synthesized answer if present
    if verdict.contradictions_detected:
        # The synthesizer may have already populated contradictions; merge without duplicates
        existing = state.contradictions  # List[ContradictionDetectedEvent]
        existing_texts = {c.nature_of_conflict for c in existing}
        for judge_contradiction in verdict.contradictions_detected:
            if judge_contradiction not in existing_texts:
                # Append to state for visibility (not as a full event, just the text)
                # The UI will surface this via JudgeRuledEvent.contradictions_detected
                pass  # Already in verdict, will be in event below

    return JudgeRuledEvent(
        judge_model=active_judge_model(),
        judge_confidence=judge_confidence,
        structural_confidence=structural_confidence,
        final_confidence=final_confidence,
        threshold=threshold,
        passed=passed,
        rationale=verdict.rationale,
        suggested_improvements=list(verdict.improvements) or None,
        # WP-5 extensions (all optional)
        coherence=verdict.coherence if verdict.coherence != 1.0 else None,
        contradictions_detected=verdict.contradictions_detected or None,
        missing_evidence=verdict.missing_evidence or None,
        # BRD-23 WP-2: shallow claim IDs forwarded via extra="allow"
        supported_but_shallow_claim_ids=verdict.supported_but_shallow_claim_ids or None,
    )


async def map_issues_to_claims(issues: list[str], sub_claims: list[SubClaim]) -> list[str]:
    """Map judge issues to the claim IDs that should be re-opened (RF-15)."""
    if not issues or not sub_claims:
        return []
    claims_block = "\n".join(f"- {c.id}: {c.text}" for c in sub_claims)
    issues_block = "\n".join(f"- {i}" for i in issues)
    user_msg = (
        "Given a list of judge issues and the current sub-claims, return the "
        "claim IDs that should be re-investigated. Only return IDs that match "
        "an existing sub-claim.\n\n"
        f"Sub-claims:\n{claims_block}\n\n"
        f"Issues:\n{issues_block}"
    )
    result = await llm.call(
        role=LLMRole.PLANNER,
        messages=[{"role": "user", "content": user_msg}],
        response_model=IssueToClaimMapping,
    )
    valid_ids = {c.id for c in sub_claims}
    return [cid for cid in result.claim_ids if cid in valid_ids]


async def draft_best_effort_fallback(
    state: RunState,
    judge_issues: list[str] | None = None,
) -> SynthesizedAnswer:
    """C3: regenerate the draft as a BEST_EFFORT answer when the judge cap fires.

    Triggered from the orchestrator when ``judge_attempts >= max_judge_attempts``.
    Instead of stopping with a stale draft the judge already rejected, we run
    the synthesizer one more time pinned to ``AnswerKind.BEST_EFFORT`` with an
    explicit fallback directive: summarise what was found, acknowledge what is
    missing, and suggest how the user can refine the question. The run still
    terminates with ``StopReason.STOPPED_BY_BUDGET`` afterwards — only the
    answer text changes from "failed draft" to "honest best-effort".
    """
    answer_kind = AnswerKind.BEST_EFFORT
    state.selected_answer_kind = answer_kind

    evidence_list = [
        {"url": e.source_url, "title": e.source_title, "snippet": e.text}
        for e in state.evidence
    ]

    # IP-25 Phase D: Format hypotheses if present
    hypotheses_list = None
    if state.hypotheses:
        hypotheses_list = [
            {"text": h.text, "priority": h.priority}
            for h in state.hypotheses
        ]

    system_prompt, max_tokens = build_synthesizer_prompt(
        question=state.question,
        evidence=evidence_list,
        answer_kind=answer_kind,
        user_language=state.language,
        requires_contradictions=False,
        hypotheses=hypotheses_list,
    )

    issues_block = ""
    if judge_issues:
        bullets = "\n".join(f"- {iss}" for iss in judge_issues[:5])
        issues_block = (
            f"\n\nThe prior synthesis was rejected by the judge "
            f"{state.judge_attempts} times. Latest issues:\n{bullets}"
        )

    fallback_directive = (
        "\n\n=== FALLBACK MODE ===\n"
        "The research loop reached its judge-attempt cap without a confirmed "
        "answer. Do NOT retry the failing strategy. Produce an HONEST "
        "best-effort answer that:\n"
        "  1. States plainly that a confident answer could not be reached.\n"
        "  2. Summarises what the evidence DID establish (if anything).\n"
        "  3. Names the specific gaps or ambiguities that blocked closure.\n"
        "  4. Offers 1-3 concrete ways the user can refine the question "
        "(narrower scope, explicit timeframe, specific entity, etc.).\n"
        "Tone: collaborative, not apologetic. Reply in the same language the user used in the question.\n"
        f"{issues_block}"
    )
    system_prompt = system_prompt + fallback_directive

    raw_payload = await llm.call(
        role=LLMRole.SYNTHESIZER,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state.question},
        ],
        response_model=_RawSynthesizerPayload,
        max_tokens=max_tokens,
    )
    payload_dict = (
        raw_payload.model_dump() if hasattr(raw_payload, "model_dump") else raw_payload
    )
    payload_dict = _coerce_synthesizer_payload(payload_dict)
    result = SynthesizedAnswer.model_validate(
        payload_dict,
        context={"_requires_contradictions": False},
    )
    # Pin the kind even if the LLM omitted it.
    result.answer_kind = answer_kind

    state.draft_answer = result.prose
    state.draft_payload = result
    state.draft_citations = list(result.citations)
    state.draft_sections = [
        AnswerSection(heading=str(idx + 1), content=kp)
        for idx, kp in enumerate(result.key_points)
    ]
    return result
