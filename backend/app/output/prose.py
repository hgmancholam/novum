"""Prose output renderer — narrative format (RF-10)."""

from __future__ import annotations

from app.seams.output import RenderContext, RenderedOutput


class ProseRenderer:
    """Renders the answer as flowing narrative text with source citations."""

    @property
    def format_name(self) -> str:
        return "prose"

    @property
    def display_name(self) -> str:
        return "Prose"

    def render(self, context: RenderContext) -> RenderedOutput:
        content = context.answer_content

        if context.sources:
            content += "\n\n---\n\n### 📚 Sources\n\n"
            content += "| # | Source |\n|---|--------|\n"
            for i, source in enumerate(context.sources, 1):
                title = source.get("title", "Untitled")
                url = source.get("url", "")
                cell = f"[{title}]({url})" if url else title
                content += f"| {i} | {cell} |\n"

        return RenderedOutput(
            format="prose",
            content=content,
            metadata={
                "word_count": len(content.split()),
                "source_count": len(context.sources),
            },
        )
