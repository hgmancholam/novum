"""Output rendering package (RF-10)."""

from app.output.prose import ProseRenderer
from app.output.registry import renderer_registry
from app.output.structured import StructuredRenderer

__all__ = ["ProseRenderer", "StructuredRenderer", "renderer_registry"]
