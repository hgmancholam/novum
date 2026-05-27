"""Structured output renderer — rich sections format (RF-10).

Renders the answer with:
- Markdown tables for key-value / comparative content
- Mermaid flowcharts for step-based / process content
- Confidence table
- Sources table
"""

from __future__ import annotations

import re

from app.seams.output import OutputRenderer, RenderContext, RenderedOutput


class StructuredRenderer:
    """Renders the answer with tables, diagrams, and organised sections."""

    @property
    def format_name(self) -> str:
        return "structured"

    @property
    def display_name(self) -> str:
        return "Structured"

    def render(self, context: RenderContext) -> RenderedOutput:
        content = self._structure_content(context.answer_content)

        # Confidence table
        content += "\n\n---\n\n### 📊 Confidence\n\n"
        content += "| Metric | Value |\n|--------|-------|\n"
        content += f"| Score | **{context.confidence:.0%}** |\n"
        content += f"| Status | {self._format_stop_reason(context.stop_reason)} |\n"

        # Sources table
        content += self._render_sources(context.sources)

        return RenderedOutput(
            format="structured",
            content=content,
            metadata={
                "sections": self._count_sections(content),
                "source_count": len(context.sources),
            },
        )

    # ------------------------------------------------------------------
    # Content structuring
    # ------------------------------------------------------------------

    def _structure_content(self, text: str) -> str:
        """Convert raw LLM text to structured markdown with tables/diagrams."""
        # Pass through already-structured content (has headers, code fences, or tables)
        if "##" in text or "```" in text:
            return text
        if "| " in text and "|---" in text:
            return text
        if "- " in text:
            return text

        paragraphs = [p.strip() for p in text.strip().split("\n\n") if p.strip()]

        if len(paragraphs) == 1:
            return f"### Summary\n\n{text}"

        # Try table format (key-value patterns)
        table_result = self._try_table_format(paragraphs)
        if table_result is not None:
            return table_result

        # Try mermaid flowchart (numbered steps / process language)
        mermaid_result = self._try_mermaid_flowchart(text)
        if mermaid_result is not None:
            return mermaid_result

        # Default: key-points bullet list
        result = "### Key Points\n\n"
        for para in paragraphs[:5]:
            summary = para[:200] + "..." if len(para) > 200 else para
            result += f"- {summary}\n"

        if len(paragraphs) > 5:
            result += "\n### Additional Details\n\n"
            result += "\n\n".join(paragraphs[5:])

        return result

    def _try_table_format(self, paragraphs: list[str]) -> str | None:
        """Detect 'Key: value' patterns and render as a markdown table."""
        kv_re = re.compile(
            r"^\*{0,2}([^:*\n]{2,50}?)\*{0,2}\s*:\s*(.+)$",
            re.MULTILINE,
        )
        kv_pairs: list[tuple[str, str]] = []
        context_paras: list[str] = []

        for para in paragraphs:
            matches = kv_re.findall(para)
            lines = para.splitlines()
            # Accept paragraph as KV if at least half lines are KV pairs
            if matches and len(matches) >= max(1, len(lines) // 2):
                kv_pairs.extend((k.strip(), v.strip()) for k, v in matches)
            else:
                context_paras.append(para)

        if len(kv_pairs) < 3:
            return None

        result = "### Summary\n\n"
        result += "| Aspect | Detail |\n|--------|--------|\n"
        for k, v in kv_pairs[:12]:
            result += f"| {k} | {v} |\n"

        if context_paras:
            result += "\n### Context\n\n"
            for para in context_paras[:3]:
                summary = para[:400] + "..." if len(para) > 400 else para
                result += f"{summary}\n\n"

        return result

    def _try_mermaid_flowchart(self, text: str) -> str | None:
        """Detect numbered/step-based content and render as a mermaid flowchart."""
        step_re = re.compile(
            r"^\s*(?:\d+[.\)]\s+|(?:Paso|Step|Etapa|Phase)\s+\d+[.:]\s*)(.+)$",
            re.MULTILINE | re.IGNORECASE,
        )
        steps = step_re.findall(text)
        if len(steps) < 3:
            return None

        result = "### Process Flow\n\n"
        result += "```mermaid\nflowchart TD\n"
        result += "    Start([▶ Start])\n"
        prev = "Start"
        for i, step_text in enumerate(steps[:8], 1):
            clean = step_text.strip()[:60].replace('"', "'")
            node_id = f"S{i}"
            result += f'    {prev} --> {node_id}["{clean}"]\n'
            prev = node_id
        result += f"    {prev} --> End([✓ End])\n```\n"

        # Append non-step context
        plain = step_re.sub("", text).strip()
        if plain:
            result += f"\n### Context\n\n{plain[:500]}\n"

        return result

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------

    def _render_sources(self, sources: list[dict]) -> str:
        """Render sources as a markdown table."""
        if not sources:
            return ""

        result = "\n\n---\n\n### 📚 Sources\n\n"
        result += "| # | Source |\n|---|--------|\n"
        for i, source in enumerate(sources, 1):
            title = source.get("title", "Untitled")
            url = source.get("url", "")
            cell = f"[{title}]({url})" if url else title
            result += f"| {i} | {cell} |\n"

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _format_stop_reason(self, reason: str) -> str:
        """Map stop_reason enum value to human-readable text (all 7 values)."""
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
