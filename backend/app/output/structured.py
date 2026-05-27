"""Structured output renderer — organized sections format (RF-10)."""

from __future__ import annotations

from app.seams.output import OutputRenderer, RenderContext, RenderedOutput


class StructuredRenderer:
    """Renders the answer with clear sections and bullet points."""

    @property
    def format_name(self) -> str:
        return "structured"

    @property
    def display_name(self) -> str:
        return "Structured"

    def render(self, context: RenderContext) -> RenderedOutput:
        content = self._structure_content(context.answer_content)

        content += "\n\n---\n\n### Confidence\n"
        content += f"- **Score**: {context.confidence:.0%}\n"
        content += f"- **Status**: {self._format_stop_reason(context.stop_reason)}\n"

        if context.sources:
            content += "\n### Sources\n"
            for source in context.sources:
                title = source.get("title", "Untitled")
                url = source.get("url", "")
                domain = source.get("domain", "")
                suffix = f" ({domain})" if domain else ""
                content += f"- [{title}]({url}){suffix}\n"

        return RenderedOutput(
            format="structured",
            content=content,
            metadata={
                "sections": self._count_sections(content),
                "source_count": len(context.sources),
            },
        )

    def _structure_content(self, text: str) -> str:
        if "##" in text or "- " in text:
            return text

        paragraphs = [p for p in text.strip().split("\n\n") if p.strip()]
        if len(paragraphs) == 1:
            return f"### Summary\n\n{text}"

        result = "### Key Points\n\n"
        for para in paragraphs[:5]:
            summary = para[:200] + "..." if len(para) > 200 else para
            result += f"- {summary}\n"

        if len(paragraphs) > 5:
            result += "\n### Additional Details\n\n"
            result += "\n\n".join(paragraphs[5:])

        return result

    def _format_stop_reason(self, reason: str) -> str:
        """Map stop_reason enum value to human-readable text (all 7 values, architecture.md Rule 3)."""
        mapping = {
            "judge_confirmed": "✅ Verified",
            "honest_unanswerable": "⚠️ Insufficient Evidence",
            "honest_contradiction": "⚠️ Conflicting Sources",
            "honest_ambiguous": "⚠️ Ambiguous Question",
            "stopped_by_budget": "ℹ️ Research Limit Reached",
            "user_cancelled": "🛑 Cancelled",
            "errored": "❌ Error",
        }
        return mapping.get(reason, reason)

    def _count_sections(self, content: str) -> int:
        return content.count("###") + content.count("## ")
