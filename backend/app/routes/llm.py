"""LLM provider catalog endpoint.

Exposes the providers compiled into the build and whether each one has
the API key configured. The frontend uses this to populate the
provider selector and disable unavailable options.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.llm.factory import available_providers

router = APIRouter(prefix="/api/llm", tags=["LLM"])


class ProviderInfo(BaseModel):
    name: str
    available: bool
    default_model: str


class ProviderListResponse(BaseModel):
    providers: list[ProviderInfo]
    default: str


@router.get("/providers", response_model=ProviderListResponse)
async def list_providers() -> ProviderListResponse:
    """Return all supported providers with their availability."""
    raw = available_providers()
    return ProviderListResponse(
        providers=[ProviderInfo(**p) for p in raw],
        default="github",
    )
