"""Output renderer registry — maps format_name → OutputRenderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.output.prose import ProseRenderer
from app.output.structured import StructuredRenderer

if TYPE_CHECKING:
    from app.seams.output import OutputRenderer


class RendererRegistry:
    def __init__(self) -> None:
        self._renderers: dict[str, OutputRenderer] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(ProseRenderer())
        self.register(StructuredRenderer())

    def register(self, renderer: OutputRenderer) -> None:
        self._renderers[renderer.format_name] = renderer

    def get(self, format_name: str) -> OutputRenderer | None:
        return self._renderers.get(format_name)

    def get_default(self) -> OutputRenderer:
        return self._renderers["prose"]

    def list_formats(self) -> list[dict]:
        return [
            {"name": r.format_name, "display": r.display_name}
            for r in self._renderers.values()
        ]


renderer_registry = RendererRegistry()
