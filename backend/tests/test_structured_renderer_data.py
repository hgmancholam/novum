"""Unit tests for the StructuredRenderer.build_data block builder (RF-10).

These tests cover the JSON contract emitted to the frontend. They are
independent from the legacy markdown ``render()`` output.
"""

from __future__ import annotations

from app.domain.structured import (
    KeyPointsBlock,
    KeyValueBlock,
    MarkdownBlock,
    MermaidBlock,
    ParagraphBlock,
    StepsBlock,
    StructuredAnswerData,
)
from app.output.structured import StructuredRenderer
from app.seams.output import RenderContext


def _ctx(text: str) -> RenderContext:
    return RenderContext(
        question="q",
        answer_content=text,
        sources=[],
        confidence=0.9,
        stop_reason="judge_confirmed",
    )


def _build(text: str) -> StructuredAnswerData:
    return StructuredRenderer().build_data(_ctx(text))


class TestExtractSummary:
    def test_first_sentence(self):
        data = _build("Tokio es la capital. Aquí hay más texto.")
        assert data.summary == "Tokio es la capital."

    def test_no_terminator_uses_first_line(self):
        data = _build("Una línea sin punto\nOtra línea")
        assert data.summary == "Una línea sin punto"

    def test_empty(self):
        data = _build("")
        assert data.summary == ""
        assert data.blocks == []


class TestSinglePhrase:
    def test_short_sentence_emits_only_summary(self):
        data = _build("La capital de Japón es Tokio.")
        assert data.summary == "La capital de Japón es Tokio."
        # Single short sentence ⇒ no extra paragraph block
        assert data.blocks == []


class TestKeyValueDetection:
    def test_key_value_block(self):
        text = (
            "Country: Japan\n"
            "Capital: Tokio\n"
            "Population: 14M\n"
            "Currency: Yen\n"
        )
        data = _build(text)
        # At least one block, and it must be a KeyValueBlock with ≥3 rows
        kv = [b for b in data.blocks if isinstance(b, KeyValueBlock)]
        assert len(kv) == 1
        assert len(kv[0].rows) >= 3
        keys = [r.key for r in kv[0].rows]
        assert "Country" in keys
        assert "Capital" in keys


class TestStepsDetection:
    def test_numbered_steps(self):
        text = (
            "Aquí tienes los pasos.\n"
            "1. Primer paso del proceso\n"
            "2. Segundo paso intermedio\n"
            "3. Tercer paso final\n"
        )
        data = _build(text)
        steps_blocks = [b for b in data.blocks if isinstance(b, StepsBlock)]
        assert len(steps_blocks) == 1
        assert len(steps_blocks[0].items) == 3


class TestBulletsDetection:
    def test_bullet_key_points(self):
        text = (
            "Resumen de hechos:\n"
            "- Primer hecho importante\n"
            "- Segundo hecho relevante\n"
            "- Tercer hecho clave\n"
        )
        data = _build(text)
        kp = [b for b in data.blocks if isinstance(b, KeyPointsBlock)]
        assert len(kp) == 1
        assert len(kp[0].items) == 3


class TestMermaidPassthrough:
    def test_extracts_mermaid_fence(self):
        text = (
            "Aquí está el flujo:\n\n"
            "```mermaid\nflowchart TD\n  A --> B\n```\n\n"
            "Y este es el resto."
        )
        data = _build(text)
        md = [b for b in data.blocks if isinstance(b, MermaidBlock)]
        assert len(md) == 1
        assert "flowchart TD" in md[0].diagram


class TestMarkdownFallback:
    def test_existing_markdown_table_is_preserved(self):
        text = (
            "Comparativa:\n\n"
            "| Lang | Year |\n"
            "|------|------|\n"
            "| Python | 1991 |\n"
            "| Go | 2009 |\n"
        )
        data = _build(text)
        mds = [b for b in data.blocks if isinstance(b, MarkdownBlock)]
        assert len(mds) == 1
        assert "| Lang" in mds[0].text

    def test_existing_md_headers_pass_through(self):
        text = "## Section\n\nSome content here."
        data = _build(text)
        mds = [b for b in data.blocks if isinstance(b, MarkdownBlock)]
        assert len(mds) == 1


class TestParagraphsFallback:
    def test_multi_paragraph_emits_paragraph_blocks(self):
        text = (
            "Primer párrafo de contexto general.\n\n"
            "Segundo párrafo añadiendo más detalles relevantes.\n\n"
            "Tercer párrafo con conclusión final del análisis."
        )
        data = _build(text)
        paras = [b for b in data.blocks if isinstance(b, ParagraphBlock)]
        # Multiple paragraphs → at least 2 paragraph blocks
        assert len(paras) >= 2


class TestRenderEmbedsData:
    def test_render_metadata_contains_data(self):
        ctx = _ctx("La capital de Japón es Tokio.")
        out = StructuredRenderer().render(ctx)
        assert "data" in out.metadata
        data = out.metadata["data"]
        assert isinstance(data, dict)
        assert data["summary"] == "La capital de Japón es Tokio."
        assert "blocks" in data


class TestKindBlocksSuppressProseFallback:
    """When the synthesizer emits typed structure (answer_kind != None),
    the prose narrative is a restatement of the same fields and must not
    be re-appended as ParagraphBlocks (would duplicate the structured
    payload in the UI)."""

    def _ctx_with_payload(self, text: str, payload):
        return RenderContext(
            question="q",
            answer_content=text,
            sources=[],
            confidence=0.9,
            stop_reason="judge_confirmed",
            synth_payload=payload,
        )

    def test_best_effort_does_not_duplicate_prose(self):
        from app.domain.enums import AnswerKind
        from app.llm.models import SynthesizedAnswer

        payload = SynthesizedAnswer(
            prose="ignored",
            answer_kind=AnswerKind.BEST_EFFORT,
            interpretation="The question asks whether AI will replace mid-level engineers.",
            alternative_interpretations=[
                "Headcount reduction interpretation.",
                "Task-level replacement interpretation.",
            ],
        )
        prose = (
            "First narrative paragraph restating the interpretation.\n\n"
            "Second paragraph with H1 hypothesis.\n\n"
            "Third paragraph with H2 hypothesis.\n\n"
            "In summary: role transformation more likely than replacement."
        )
        ctx = self._ctx_with_payload(prose, payload)
        data = StructuredRenderer().build_data(ctx)

        # Typed blocks must be present (interpretation + alternatives)
        paras = [b for b in data.blocks if isinstance(b, ParagraphBlock)]
        kps = [b for b in data.blocks if isinstance(b, KeyPointsBlock)]
        assert any("Most likely interpretation" in p.text for p in paras)
        assert any(kp.title == "Alternative interpretations" for kp in kps)

        # Prose must NOT be re-emitted as additional paragraph blocks
        assert not any("H1 hypothesis" in p.text for p in paras)
        assert not any("In summary" in p.text for p in paras)

    def test_kind_blocks_still_preserve_mermaid_and_markdown(self):
        """Mermaid fences and markdown tables/headers must survive even
        when kind_blocks are emitted — they are LLM-authored formatting,
        not a textual restatement."""
        from app.domain.enums import AnswerKind
        from app.llm.models import SynthesizedAnswer

        payload = SynthesizedAnswer(
            prose="ignored",
            answer_kind=AnswerKind.BEST_EFFORT,
            interpretation="Some interpretation.",
            alternative_interpretations=["Alt one."],
        )
        text_with_mermaid = (
            "Diagrama:\n\n"
            "```mermaid\nflowchart TD\n  A --> B\n```\n\n"
            "Texto que ahora se descarta."
        )
        ctx = self._ctx_with_payload(text_with_mermaid, payload)
        data = StructuredRenderer().build_data(ctx)
        mer = [b for b in data.blocks if isinstance(b, MermaidBlock)]
        assert len(mer) == 1

        text_with_md_table = (
            "Comparativa:\n\n"
            "| Lang | Year |\n|------|------|\n| Python | 1991 |\n| Go | 2009 |\n"
        )
        ctx2 = self._ctx_with_payload(text_with_md_table, payload)
        data2 = StructuredRenderer().build_data(ctx2)
        mds = [b for b in data2.blocks if isinstance(b, MarkdownBlock)]
        assert len(mds) == 1

    def test_no_kind_payload_keeps_paragraph_fallback(self):
        """Sanity: without answer_kind, behavior is unchanged."""
        prose = (
            "Primer párrafo de contexto general.\n\n"
            "Segundo párrafo con detalles.\n\n"
            "Tercer párrafo con conclusión."
        )
        data = _build(prose)  # no synth_payload
        paras = [b for b in data.blocks if isinstance(b, ParagraphBlock)]
        assert len(paras) >= 2
