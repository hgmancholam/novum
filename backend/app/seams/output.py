"""OutputRenderer plugin seam — one of three extensibility points (architecture.md Rule 1).

Renderers format the final answer for display. Rendering is SYNCHRONOUS
(no LLM calls allowed on the read path).

V1: Prose, Structured
V2: Table, Timeline, Comparison Matrix
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class RenderContext(BaseModel):
    """Context passed to a renderer at answer-stop time."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    question: str
    answer_content: str
    sources: list[dict]  # [{"url": str, "title": str, "domain": str}]
    confidence: float
    stop_reason: str
    # PR-2 Mejora 1.2: full typed synthesizer payload (SynthesizedAnswer) with
    # ``answer_kind`` and kind-specific fields. Typed as ``Any`` so Pydantic
    # does not re-run the kind-specific validator on a previously-mutated
    # instance (e.g. answer_kind stamped after construction); the renderer
    # narrows it back via getattr.
    synth_payload: Any = None


class RenderedOutput(BaseModel):
    """Output produced by a renderer."""

    model_config = ConfigDict(extra="allow")

    format: str
    content: str
    metadata: dict = {}


@runtime_checkable
class OutputRenderer(Protocol):
    """Protocol for output renderer plugins (RF-10)."""

    @property
    def format_name(self) -> str:
        """Unique format identifier (lowercase, no spaces)."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable label shown in the UI."""
        ...

    def render(self, context: RenderContext) -> RenderedOutput:
        """Render the answer.

        This method MUST be synchronous — no async, no LLM calls.
        Rendering must be deterministic (same input → same output).
        """
        ...
