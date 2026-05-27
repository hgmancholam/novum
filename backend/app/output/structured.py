"""Structured output renderer — rich sections format (RF-10).

Produces TWO artefacts from the same answer text:

1. ``content``  — markdown string (legacy, kept for back-compat / fallback)
2. ``data``     — typed :class:`StructuredAnswerData` JSON the frontend
                  renders with native UI components (no markdown parsing).

The block builder is deterministic and synchronous (no LLM calls on the
read path, RF-10).
"""

from __future__ import annotations

import re

from app.domain.structured import (
    KeyPointsBlock,
    KeyValueBlock,
    KeyValueRow,
    MarkdownBlock,
    MermaidBlock,
    ParagraphBlock,
    StepsBlock,
    StructuredAnswerData,
    StructuredBlock,
)
from app.seams.output import RenderContext, RenderedOutput


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

        data = self.build_data(context)

        return RenderedOutput(
            format="structured",
            content=content,
            metadata={
                "sections": self._count_sections(content),
                "source_count": len(context.sources),
                "data": data.model_dump(mode="json"),
            },
        )

    # ------------------------------------------------------------------
    # JSON block builder (FE/BE contract)
    # ------------------------------------------------------------------

    def build_data(self, context: RenderContext) -> StructuredAnswerData:
        """Convert raw LLM answer text into a typed block sequence.

        The frontend renders each block with native UI elements (tables,
        ordered lists, Mermaid diagrams). This keeps presentation logic in
        the client and content extraction in the server.
        """
        text = (context.answer_content or "").strip()
        summary = self._extract_summary(text)
        blocks: list[StructuredBlock] = []

        if not text:
            return StructuredAnswerData(summary=summary, blocks=blocks)

        # 1. Pull out fenced mermaid blocks (preserve them as MermaidBlock).
        mermaid_re = re.compile(r"```mermaid\s*\n(.+?)\n```", re.DOTALL)
        mermaid_matches = list(mermaid_re.finditer(text))
        residual = mermaid_re.sub("", text).strip()
        for m in mermaid_matches:
            blocks.append(MermaidBlock(diagram=m.group(1).strip()))

        # 2. If the LLM emitted markdown tables or headers, keep them
        #    intact in a MarkdownBlock (frontend renders markdown).
        has_md_table = bool(re.search(r"^\|.+\|\s*$", residual, re.MULTILINE)) and "|---" in residual
        has_md_headers = bool(re.search(r"^#{1,6}\s", residual, re.MULTILINE))
        has_fence = "```" in residual
        if residual and (has_md_table or has_md_headers or has_fence):
            blocks.append(MarkdownBlock(text=residual))
            return StructuredAnswerData(summary=summary, blocks=blocks)

        # 3. Try key/value extraction.
        kv_block = self._extract_key_value(residual)
        if kv_block is not None:
            blocks.append(kv_block)
            return StructuredAnswerData(summary=summary, blocks=blocks)

        # 4. Try numbered/process steps.
        steps_block = self._extract_steps(residual)
        if steps_block is not None:
            blocks.append(steps_block)
            return StructuredAnswerData(summary=summary, blocks=blocks)

        # 5. Bullet-style key points (lines starting with -, *, or •).
        points = self._extract_bullets(residual)
        if points is not None:
            blocks.append(points)
            return StructuredAnswerData(summary=summary, blocks=blocks)

        # 6. Default: split into paragraphs.
        paragraphs = [p.strip() for p in residual.split("\n\n") if p.strip()]
        if len(paragraphs) <= 1:
            # Single sentence ≈ summary; emit one paragraph for legibility.
            if residual and residual != summary:
                blocks.append(ParagraphBlock(text=residual))
        else:
            for para in paragraphs:
                blocks.append(ParagraphBlock(text=para))

        return StructuredAnswerData(summary=summary, blocks=blocks)

    # ------------------------------------------------------------------
    # Block extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_summary(text: str) -> str:
        """First sentence (up to ~280 chars) — used as headline."""
        cleaned = text.strip()
        if not cleaned:
            return ""
        match = re.match(r"^([^.!?\n]{5,280}[.!?])", cleaned)
        if match:
            return match.group(1).strip()
        # Fallback: first non-empty line clipped.
        first_line = cleaned.splitlines()[0].strip()
        return first_line[:200]

    @staticmethod
    def _extract_key_value(text: str) -> KeyValueBlock | None:
        kv_re = re.compile(
            r"^\*{0,2}([^:*\n]{2,50}?)\*{0,2}\s*:\s*(.+)$",
            re.MULTILINE,
        )
        pairs = kv_re.findall(text)
        if len(pairs) < 3:
            return None
        rows = [KeyValueRow(key=k.strip(), value=v.strip()) for k, v in pairs[:12]]
        return KeyValueBlock(title="Key facts", rows=rows)

    @staticmethod
    def _extract_steps(text: str) -> StepsBlock | None:
        step_re = re.compile(
            r"^\s*(?:\d+[.\)]\s+|(?:Paso|Step|Etapa|Phase)\s+\d+[.:]\s*)(.+)$",
            re.MULTILINE | re.IGNORECASE,
        )
        steps = [s.strip() for s in step_re.findall(text) if s.strip()]
        if len(steps) < 3:
            return None
        return StepsBlock(title="Steps", items=steps[:10])

    @staticmethod
    def _extract_bullets(text: str) -> KeyPointsBlock | None:
        bullet_re = re.compile(r"^\s*[-*•]\s+(.+)$", re.MULTILINE)
        items = [b.strip() for b in bullet_re.findall(text) if b.strip()]
        if len(items) < 2:
            return None
        return KeyPointsBlock(title="Key points", items=items[:10])

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
        """Map stop_reason enum value to human-readable text (WP-3: 4 values)."""
        mapping = {
            "judge_confirmed": "✅ Verified",
            "stopped_by_budget": "ℹ️ Research Limit Reached",
            "user_cancelled": "🛑 Cancelled",
            "errored": "❌ Error",
        }
        return mapping.get(reason, reason)

    def _count_sections(self, content: str) -> int:
        return content.count("###") + content.count("## ")
