# BRD-16: Output Format Renderers

**Document ID:** BRD-16
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 17 of 19

---

## 1. Executive Summary

Implement the OutputRenderer plugin seam per RF-10, supporting prose and structured output formats. Users select the desired format before starting research, and the answer is rendered accordingly.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-10 | Output format selection | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-05, BRD-07, BRD-13 | Complete |

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    seams/
      output.py             # OutputRenderer protocol
    output/
      __init__.py
      prose.py              # Prose renderer
      structured.py         # Structured renderer
      registry.py           # Renderer registry
frontend/
  src/
    components/
      molecules/
        FormatSelector.tsx
      organisms/
        StructuredAnswer.tsx
```

### 4.2 Output Formats (RF-10)

| Format | Description | Use Case |
|--------|-------------|----------|
| prose | Narrative paragraphs | General questions |
| structured | Bullet points, sections | Technical comparisons |

### 4.3 OutputRenderer Protocol

#### backend/app/seams/output.py

```python
"""OutputRenderer plugin seam — one of three extensibility points.

Renderers format the final answer for display.
V1: Prose, Structured
V2: Table, Timeline, Comparison Matrix
"""

from abc import abstractmethod
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class RenderContext(BaseModel):
    """Context for rendering."""

    question: str
    answer_content: str
    sources: list[dict]
    confidence: float
    stop_reason: str


class RenderedOutput(BaseModel):
    """Output from a renderer."""

    format: str
    content: str
    metadata: dict = {}


@runtime_checkable
class OutputRenderer(Protocol):
    """Protocol for output renderer plugins."""

    @property
    def format_name(self) -> str:
        """Unique format identifier."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable name."""
        ...

    def render(self, context: RenderContext) -> RenderedOutput:
        """Render the answer.
        
        This is synchronous because rendering should be deterministic
        and fast (no LLM calls on read path).
        """
        ...
```

### 4.4 Prose Renderer

#### backend/app/output/prose.py

```python
"""Prose output renderer — narrative format."""

from app.seams.output import OutputRenderer, RenderContext, RenderedOutput


class ProseRenderer:
    """Renders answer as flowing narrative text."""

    @property
    def format_name(self) -> str:
        return "prose"

    @property
    def display_name(self) -> str:
        return "Prose"

    def render(self, context: RenderContext) -> RenderedOutput:
        """Render as prose.
        
        The answer_content is already in prose form from the LLM.
        This renderer adds source citations at the end.
        """
        content = context.answer_content

        # Add sources section
        if context.sources:
            content += "\n\n---\n\n### Sources\n"
            for i, source in enumerate(context.sources, 1):
                title = source.get("title", "Untitled")
                url = source.get("url", "")
                content += f"{i}. [{title}]({url})\n"

        return RenderedOutput(
            format="prose",
            content=content,
            metadata={
                "word_count": len(content.split()),
                "source_count": len(context.sources),
            },
        )
```

### 4.5 Structured Renderer

#### backend/app/output/structured.py

```python
"""Structured output renderer — organized format."""

from app.seams.output import OutputRenderer, RenderContext, RenderedOutput


class StructuredRenderer:
    """Renders answer with clear sections and bullet points."""

    @property
    def format_name(self) -> str:
        return "structured"

    @property
    def display_name(self) -> str:
        return "Structured"

    def render(self, context: RenderContext) -> RenderedOutput:
        """Render as structured output.
        
        Parses the answer_content and reformats into sections.
        """
        content = self._structure_content(context.answer_content)

        # Add confidence section
        content += f"\n\n---\n\n### Confidence\n"
        content += f"- **Score**: {context.confidence:.0%}\n"
        content += f"- **Status**: {self._format_stop_reason(context.stop_reason)}\n"

        # Add sources section
        if context.sources:
            content += "\n### Sources\n"
            for source in context.sources:
                title = source.get("title", "Untitled")
                url = source.get("url", "")
                domain = source.get("domain", "")
                content += f"- [{title}]({url}) ({domain})\n"

        return RenderedOutput(
            format="structured",
            content=content,
            metadata={
                "sections": self._count_sections(content),
                "source_count": len(context.sources),
            },
        )

    def _structure_content(self, text: str) -> str:
        """Convert prose to structured format if needed."""
        # If already has headers, return as-is
        if "##" in text or "- " in text:
            return text

        # Split into paragraphs and convert
        paragraphs = text.strip().split("\n\n")
        if len(paragraphs) == 1:
            return f"### Summary\n\n{text}"

        result = "### Key Points\n\n"
        for para in paragraphs[:5]:  # Limit to 5 key points
            # Convert paragraph to bullet point
            summary = para[:200] + "..." if len(para) > 200 else para
            result += f"- {summary}\n"

        if len(paragraphs) > 5:
            result += "\n### Additional Details\n\n"
            result += "\n\n".join(paragraphs[5:])

        return result

    def _format_stop_reason(self, reason: str) -> str:
        """Format stop reason for display."""
        mapping = {
            "judge_confirmed": "✅ Verified",
            "honest_unanswerable": "⚠️ Insufficient Evidence",
            "honest_contradiction": "⚠️ Conflicting Sources",
            "honest_ambiguous": "⚠️ Ambiguous Question",
            "stopped_by_budget": "ℹ️ Research Limit",
            "user_cancelled": "🛑 Cancelled",
            "errored": "❌ Error",
        }
        return mapping.get(reason, reason)

    def _count_sections(self, content: str) -> int:
        """Count markdown sections."""
        return content.count("###") + content.count("##")
```

### 4.6 Renderer Registry

#### backend/app/output/registry.py

```python
"""Output renderer registry."""

from typing import Dict, Optional

from app.seams.output import OutputRenderer
from app.output.prose import ProseRenderer
from app.output.structured import StructuredRenderer


class RendererRegistry:
    """Registry of available output renderers."""

    def __init__(self) -> None:
        self._renderers: Dict[str, OutputRenderer] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register built-in renderers."""
        self.register(ProseRenderer())
        self.register(StructuredRenderer())

    def register(self, renderer: OutputRenderer) -> None:
        """Register a renderer."""
        self._renderers[renderer.format_name] = renderer

    def get(self, format_name: str) -> Optional[OutputRenderer]:
        """Get a renderer by format name."""
        return self._renderers.get(format_name)

    def get_default(self) -> OutputRenderer:
        """Get the default renderer (prose)."""
        return self._renderers["prose"]

    def list_formats(self) -> list[dict]:
        """List available formats."""
        return [
            {"name": r.format_name, "display": r.display_name}
            for r in self._renderers.values()
        ]


# Singleton
renderer_registry = RendererRegistry()
```

### 4.7 Package Exports

#### backend/app/output/__init__.py

```python
"""Output rendering package."""

from app.output.prose import ProseRenderer
from app.output.structured import StructuredRenderer
from app.output.registry import renderer_registry

__all__ = [
    "ProseRenderer",
    "StructuredRenderer",
    "renderer_registry",
]
```

### 4.8 API Endpoint for Formats

#### backend/app/routes/formats.py

```python
"""Output format endpoints."""

from fastapi import APIRouter

from app.output import renderer_registry

router = APIRouter(prefix="/api/formats", tags=["Formats"])


@router.get("")
async def list_formats():
    """List available output formats."""
    return {"formats": renderer_registry.list_formats()}
```

### 4.9 Frontend Format Selector

#### frontend/src/components/molecules/FormatSelector.tsx

```typescript
/**
 * Output format selector component.
 */

import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/cn";

interface Format {
  name: string;
  display: string;
}

interface FormatSelectorProps {
  value: string;
  onChange: (format: string) => void;
  className?: string;
}

async function fetchFormats(): Promise<Format[]> {
  const response = await fetch(`${import.meta.env.VITE_API_URL}/api/formats`);
  if (!response.ok) throw new Error("Failed to fetch formats");
  const data = await response.json();
  return data.formats;
}

export function FormatSelector({
  value,
  onChange,
  className,
}: FormatSelectorProps) {
  const { data: formats = [], isLoading } = useQuery({
    queryKey: ["formats"],
    queryFn: fetchFormats,
  });

  if (isLoading) {
    return (
      <div className={cn("animate-pulse rounded bg-gray-200 h-10", className)} />
    );
  }

  return (
    <div className={cn("flex gap-2", className)}>
      {formats.map((format) => (
        <button
          key={format.name}
          onClick={() => onChange(format.name)}
          className={cn(
            "rounded-lg px-4 py-2 text-sm font-medium transition-colors",
            value === format.name
              ? "bg-blue-600 text-white"
              : "bg-gray-100 text-gray-700 hover:bg-gray-200"
          )}
        >
          {format.display}
        </button>
      ))}
    </div>
  );
}
```

### 4.10 Structured Answer Component

#### frontend/src/components/organisms/StructuredAnswer.tsx

```typescript
/**
 * Enhanced structured answer display.
 */

import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/cn";

interface StructuredAnswerProps {
  content: string;
  metadata?: {
    sections?: number;
    source_count?: number;
  };
}

export function StructuredAnswer({ content, metadata }: StructuredAnswerProps) {
  return (
    <div className="space-y-4">
      {/* Stats bar */}
      {metadata && (
        <div className="flex gap-4 text-sm text-gray-500">
          {metadata.sections && (
            <span>{metadata.sections} sections</span>
          )}
          {metadata.source_count && (
            <span>{metadata.source_count} sources</span>
          )}
        </div>
      )}

      {/* Content */}
      <div className="prose prose-gray max-w-none prose-headings:text-lg prose-ul:my-2">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    </div>
  );
}
```

---

## 5. Acceptance Criteria

### AC-01: Format Selection Available
```gherkin
Given I am on the home page
When I prepare to ask a question
Then I see format selector with "Prose" and "Structured" options
  And "Prose" is selected by default
```

### AC-02: Prose Format Renders Narrative
```gherkin
Given I selected "Prose" format
When the research completes
Then the answer displays as flowing paragraphs
  And sources are listed at the end
```

### AC-03: Structured Format Has Sections
```gherkin
Given I selected "Structured" format
When the research completes
Then the answer has "Key Points" section with bullets
  And confidence and sources sections are visible
```

### AC-04: Format Stored with Run
```gherkin
Given I selected "Structured" format
When I view the run later
Then it still displays in structured format
```

---

## 6. Implementation Checklist

- [ ] Create `backend/app/seams/output.py`
- [ ] Create `backend/app/output/__init__.py`
- [ ] Create `backend/app/output/prose.py`
- [ ] Create `backend/app/output/structured.py`
- [ ] Create `backend/app/output/registry.py`
- [ ] Create `backend/app/routes/formats.py`
- [ ] Create `frontend/src/components/molecules/FormatSelector.tsx`
- [ ] Create `frontend/src/components/organisms/StructuredAnswer.tsx`
- [ ] Update HomePage with format selector
- [ ] Update AnswerDisplay to use renderers
- [ ] Write unit tests

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit | pytest | Each renderer | 100% |
| Unit | Vitest + RTL | FormatSelector | 100% |

## 8. Environment Variables

_None required._

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Format mismatch on view | Low | Low | Store format in run |

## 10. Out of Scope

- Table format
- Timeline format
- Custom format templates
