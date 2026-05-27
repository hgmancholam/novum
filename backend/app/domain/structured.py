"""Structured answer JSON schema (RF-10, BRD-16).

Backend produces this JSON; frontend renders it with native UI components
(tables, lists, diagrams). This is the source of truth for the FE/BE contract
on structured answer rendering.

Renderers MUST keep the model deterministic: same input → same output.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class KeyValueRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str
    value: str


class ParagraphBlock(BaseModel):
    """A plain prose paragraph rendered as styled text."""

    model_config = ConfigDict(extra="allow")

    type: Literal["paragraph"] = "paragraph"
    text: str


class KeyValueBlock(BaseModel):
    """Key/value table — for facts, attributes, specs."""

    model_config = ConfigDict(extra="allow")

    type: Literal["keyValue"] = "keyValue"
    title: str | None = None
    rows: list[KeyValueRow]


class StepsBlock(BaseModel):
    """Ordered list of steps / process stages."""

    model_config = ConfigDict(extra="allow")

    type: Literal["steps"] = "steps"
    title: str | None = None
    items: list[str]


class KeyPointsBlock(BaseModel):
    """Unordered list of key points / bullets."""

    model_config = ConfigDict(extra="allow")

    type: Literal["keyPoints"] = "keyPoints"
    title: str | None = None
    items: list[str]


class MermaidBlock(BaseModel):
    """Mermaid diagram source (flowchart, sequence, etc.)."""

    model_config = ConfigDict(extra="allow")

    type: Literal["mermaid"] = "mermaid"
    title: str | None = None
    diagram: str


class MarkdownBlock(BaseModel):
    """Fallback for content that is already richly formatted by the LLM."""

    model_config = ConfigDict(extra="allow")

    type: Literal["markdown"] = "markdown"
    text: str


StructuredBlock = Annotated[
    ParagraphBlock
    | KeyValueBlock
    | StepsBlock
    | KeyPointsBlock
    | MermaidBlock
    | MarkdownBlock,
    Field(discriminator="type"),
]


class StructuredAnswerData(BaseModel):
    """Structured-format answer payload (RF-10).

    The frontend renders each block with native UI components instead of
    parsing markdown. ``summary`` is shown as a headline above the blocks.
    """

    model_config = ConfigDict(extra="allow")

    summary: str
    blocks: list[StructuredBlock] = Field(default_factory=list)
