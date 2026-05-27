"""Unit tests for OutputRenderer seam and built-in renderers (BRD-16)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.output.prose import ProseRenderer
from app.output.registry import RendererRegistry, renderer_registry
from app.output.structured import StructuredRenderer
from app.seams.output import OutputRenderer, RenderContext, RenderedOutput


def make_context(
    answer_content: str = "Test answer",
    sources: list | None = None,
    confidence: float = 0.85,
    stop_reason: str = "judge_confirmed",
) -> RenderContext:
    return RenderContext(
        question="What is Python?",
        answer_content=answer_content,
        sources=sources or [],
        confidence=confidence,
        stop_reason=stop_reason,
    )


class TestProseRenderer:
    def test_format_name(self):
        assert ProseRenderer().format_name == "prose"

    def test_display_name(self):
        assert ProseRenderer().display_name == "Prose"

    def test_no_sources_passthrough(self):
        renderer = ProseRenderer()
        ctx = make_context("Hello world.")
        out = renderer.render(ctx)
        assert out.format == "prose"
        assert "Hello world." in out.content
        assert "Sources" not in out.content

    def test_sources_appended(self):
        renderer = ProseRenderer()
        ctx = make_context(
            "Hello.",
            sources=[
                {"url": "https://example.com", "title": "Example", "domain": ""}
            ],
        )
        out = renderer.render(ctx)
        assert "### 📚 Sources" in out.content
        assert "Example" in out.content
        assert "https://example.com" in out.content

    def test_metadata_word_count(self):
        renderer = ProseRenderer()
        ctx = make_context("one two three")
        out = renderer.render(ctx)
        assert out.metadata["source_count"] == 0
        assert isinstance(out.metadata["word_count"], int)
        assert out.metadata["word_count"] >= 3

    def test_metadata_source_count(self):
        renderer = ProseRenderer()
        ctx = make_context(
            sources=[
                {"url": "u1", "title": "t1", "domain": ""},
                {"url": "u2", "title": "t2", "domain": ""},
            ]
        )
        out = renderer.render(ctx)
        assert out.metadata["source_count"] == 2

    def test_implements_protocol(self):
        assert isinstance(ProseRenderer(), OutputRenderer)


class TestStructuredRenderer:
    def test_format_name(self):
        assert StructuredRenderer().format_name == "structured"

    def test_display_name(self):
        assert StructuredRenderer().display_name == "Structured"

    def test_plain_text_to_key_points(self):
        renderer = StructuredRenderer()
        ctx = make_context("para one\n\npara two\n\npara three")
        out = renderer.render(ctx)
        assert "Key Points" in out.content

    def test_existing_headers_passthrough(self):
        renderer = StructuredRenderer()
        ctx = make_context("## My Section\n\nContent here.")
        out = renderer.render(ctx)
        assert "## My Section" in out.content

    def test_confidence_section(self):
        renderer = StructuredRenderer()
        ctx = make_context(confidence=0.85, stop_reason="judge_confirmed")
        out = renderer.render(ctx)
        assert "Confidence" in out.content
        assert "85%" in out.content
        assert "Verified" in out.content

    def test_all_stop_reasons_mapped(self):
        renderer = StructuredRenderer()
        for reason in [
            "judge_confirmed",
            "honest_unanswerable",
            "honest_contradiction",
            "honest_ambiguous",
            "stopped_by_budget",
            "user_cancelled",
            "errored",
        ]:
            ctx = make_context(stop_reason=reason)
            out = renderer.render(ctx)
            # Ensure we don't get raw enum value back
            assert renderer._format_stop_reason(reason) != reason

    def test_sources_section(self):
        renderer = StructuredRenderer()
        ctx = make_context(
            sources=[{"url": "https://x.com", "title": "X", "domain": "x.com"}]
        )
        out = renderer.render(ctx)
        assert "Sources" in out.content
        assert "X" in out.content

    def test_metadata_sections_count(self):
        renderer = StructuredRenderer()
        ctx = make_context("para one\n\npara two")
        out = renderer.render(ctx)
        assert isinstance(out.metadata["sections"], int)
        assert out.metadata["sections"] >= 1

    def test_implements_protocol(self):
        assert isinstance(StructuredRenderer(), OutputRenderer)

    def test_empty_paragraphs_filtered(self):
        renderer = StructuredRenderer()
        ctx = make_context("para one\n\n\n\npara two")
        out = renderer.render(ctx)
        assert "Key Points" in out.content


class TestRendererRegistry:
    def test_list_formats_returns_two(self):
        reg = RendererRegistry()
        formats = reg.list_formats()
        assert len(formats) == 2
        names = [f["name"] for f in formats]
        assert "prose" in names
        assert "structured" in names

    def test_get_default_is_prose(self):
        reg = RendererRegistry()
        assert reg.get_default().format_name == "prose"

    def test_get_by_name(self):
        reg = RendererRegistry()
        assert reg.get("structured").format_name == "structured"  # type: ignore
        assert reg.get("prose").format_name == "prose"  # type: ignore

    def test_unknown_format_returns_none(self):
        reg = RendererRegistry()
        assert reg.get("table") is None

    def test_singleton_is_populated(self):
        assert renderer_registry.get("prose") is not None
        assert renderer_registry.get("structured") is not None


class TestFormatsEndpoint:
    def test_list_formats_200(self):
        client = TestClient(app)
        response = client.get("/api/formats")
        assert response.status_code == 200
        data = response.json()
        assert "formats" in data
        assert len(data["formats"]) == 2
        names = [f["name"] for f in data["formats"]]
        assert "prose" in names
        assert "structured" in names
