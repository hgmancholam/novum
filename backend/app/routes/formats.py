"""Output format discovery endpoint (BRD-16 §4.8)."""

from __future__ import annotations

from fastapi import APIRouter

from app.output import renderer_registry

router = APIRouter(prefix="/api/formats", tags=["Formats"])


@router.get("")
async def list_formats() -> dict:
    """List available output formats (RF-10)."""
    return {"formats": renderer_registry.list_formats()}
