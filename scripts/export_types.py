#!/usr/bin/env python3
"""Export Pydantic domain models to TypeScript types.

Generates ``frontend/src/types/events.ts`` from the backend domain layer
(BRD-02). Run this whenever event models change.

Usage:
    python scripts/export_types.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make ``app`` importable when running the script from the repo root.
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(_BACKEND))

from pydantic import TypeAdapter  # noqa: E402

from app.domain.enums import (  # noqa: E402
    ComplexityHint,
    EventType,
    EvidencePolarity,
    OutputFormat,
    QuestionType,
    SourceType,
    StopReason,
)
from app.domain.events import FORKABLE_EVENTS, Event  # noqa: E402
from app.domain.structured import StructuredAnswerData  # noqa: E402

_OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent / "frontend" / "src" / "types" / "events.ts"
)


def _render_enum(name: str, values: list[str]) -> str:
    """Render a StrEnum as a string-literal TypeScript union."""
    literals = "\n  | ".join(f'"{v}"' for v in values)
    return f"export type {name} =\n  | {literals};\n"


def _build_output() -> str:
    """Build the contents of events.ts."""
    enums: list[tuple[str, list[str]]] = [
        ("StopReason", [v.value for v in StopReason]),
        ("QuestionType", [v.value for v in QuestionType]),
        ("OutputFormat", [v.value for v in OutputFormat]),
        ("EvidencePolarity", [v.value for v in EvidencePolarity]),
        ("SourceType", [v.value for v in SourceType]),
        ("EventType", [v.value for v in EventType]),
        ("ComplexityHint", [v.value for v in ComplexityHint]),
    ]

    adapter: TypeAdapter[Event] = TypeAdapter(Event)
    schema = adapter.json_schema(mode="serialization")

    timestamp = datetime.now(timezone.utc).isoformat()

    lines: list[str] = []
    lines.append("// Auto-generated from Pydantic models — DO NOT EDIT")
    lines.append("// Source: scripts/export_types.py (BRD-02)")
    lines.append(f"// Generated: {timestamp}")
    lines.append("")
    lines.append("// ---------------------------------------------------------------------------")
    lines.append("// Enums")
    lines.append("// ---------------------------------------------------------------------------")
    lines.append("")
    for name, values in enums:
        lines.append(_render_enum(name, values))

    lines.append("// ---------------------------------------------------------------------------")
    lines.append("// Forkable events (RF-03): user-selectable branch points.")
    lines.append("// ---------------------------------------------------------------------------")
    lines.append("")
    forkable = [e.value for e in EventType if e in FORKABLE_EVENTS]
    forkable_literals = ", ".join(f'"{v}"' for v in forkable)
    lines.append(
        f"export const FORKABLE_EVENTS: readonly EventType[] = [{forkable_literals}] as const;"
    )
    lines.append("")

    lines.append("// ---------------------------------------------------------------------------")
    lines.append("// Structured answer payload (RF-10, BRD-16)")
    lines.append("// Source: app/domain/structured.py")
    lines.append("// ---------------------------------------------------------------------------")
    lines.append("")
    lines.append("export interface KeyValueRow {")
    lines.append("  key: string;")
    lines.append("  value: string;")
    lines.append("}")
    lines.append("")
    lines.append("export interface ParagraphBlock {")
    lines.append('  type: "paragraph";')
    lines.append("  text: string;")
    lines.append("}")
    lines.append("")
    lines.append("export interface KeyValueBlock {")
    lines.append('  type: "keyValue";')
    lines.append("  title?: string | null;")
    lines.append("  rows: KeyValueRow[];")
    lines.append("}")
    lines.append("")
    lines.append("export interface StepsBlock {")
    lines.append('  type: "steps";')
    lines.append("  title?: string | null;")
    lines.append("  items: string[];")
    lines.append("}")
    lines.append("")
    lines.append("export interface KeyPointsBlock {")
    lines.append('  type: "keyPoints";')
    lines.append("  title?: string | null;")
    lines.append("  items: string[];")
    lines.append("}")
    lines.append("")
    lines.append("export interface MermaidBlock {")
    lines.append('  type: "mermaid";')
    lines.append("  title?: string | null;")
    lines.append("  diagram: string;")
    lines.append("}")
    lines.append("")
    lines.append("export interface MarkdownBlock {")
    lines.append('  type: "markdown";')
    lines.append("  text: string;")
    lines.append("}")
    lines.append("")
    lines.append("export type StructuredBlock =")
    lines.append("  | ParagraphBlock")
    lines.append("  | KeyValueBlock")
    lines.append("  | StepsBlock")
    lines.append("  | KeyPointsBlock")
    lines.append("  | MermaidBlock")
    lines.append("  | MarkdownBlock;")
    lines.append("")
    lines.append("export interface StructuredAnswerData {")
    lines.append("  summary: string;")
    lines.append("  blocks: StructuredBlock[];")
    lines.append("}")
    lines.append("")
    _ = StructuredAnswerData  # ensure import is used (schema embedded below)

    lines.append("// ---------------------------------------------------------------------------")
    lines.append("// JSON Schema for runtime validation")
    lines.append("// ---------------------------------------------------------------------------")
    lines.append("")
    lines.append(f"export const EventSchema = {json.dumps(schema, indent=2)} as const;")
    lines.append("")

    lines.append("// ---------------------------------------------------------------------------")
    lines.append("// Event union (informational — concrete interfaces live in the JSON schema).")
    lines.append("// Use `EventType` for narrowing and `EventSchema` for runtime validation.")
    lines.append("// ---------------------------------------------------------------------------")
    lines.append("//")
    lines.append("// Event =")
    for i, event_type in enumerate(EventType):
        sep = "//   |" if i > 0 else "//    "
        lines.append(f"{sep} {event_type.value}Event")
    lines.append("//   ;")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Write the TypeScript types file."""
    output = _build_output()
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text(output, encoding="utf-8")
    print(f"Wrote {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
