"""Tenacity retry configuration for LLM calls.

Per IP-05 §5 step 4: retries transient HTTP failures from the LLM
gateway with exponential backoff. ``before_sleep_log`` requires a
``logging`` level integer; BRD-05 §4.4 mistakenly passes ``"warning"``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from collections.abc import Callable

_stdlib_logger = logging.getLogger("app.llm.retry")

RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.HTTPStatusError,
)


def create_retry_decorator(max_attempts: int = 3) -> Callable[..., Any]:
    """Build a tenacity retry decorator with exponential backoff."""
    return retry(
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before_sleep=before_sleep_log(_stdlib_logger, logging.WARNING),
        reraise=True,
    )


retry_llm: Callable[..., Any] = create_retry_decorator(max_attempts=3)
retry_llm_critical: Callable[..., Any] = create_retry_decorator(max_attempts=5)
