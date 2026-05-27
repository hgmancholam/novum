"""Tenacity retry configuration for LLM calls.

Per IP-05 §5 step 4: retries transient HTTP failures from the LLM
gateway with exponential backoff. ``before_sleep_log`` requires a
``logging`` level integer; BRD-05 §4.4 mistakenly passes ``"warning"``.

GitHub Models enforces per-minute quotas; ``RateLimitError`` is treated
as retryable with a longer backoff window (the free tier resets every
60 s, so 1 s -> 60 s exponential covers a full quota window).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx
import litellm
from instructor.core import InstructorRetryException
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
    litellm.RateLimitError,
    # Instructor wraps every underlying exception (including
    # ``RateLimitError``) in ``InstructorRetryException`` after its own
    # internal retry loop gives up. We still want tenacity to take over
    # so that ``LLMClient.call`` is re-entered, which rotates to the
    # next model in the pool.
    InstructorRetryException,
)


def create_retry_decorator(max_attempts: int = 5) -> Callable[..., Any]:
    """Build a tenacity retry decorator with exponential backoff.

    Default of 5 attempts with 1->60 s exponential backoff is sized for
    GitHub Models' 60 s per-minute quota window.
    """
    return retry(
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=2, min=1, max=60),
        before_sleep=before_sleep_log(_stdlib_logger, logging.WARNING),
        reraise=True,
    )


retry_llm: Callable[..., Any] = create_retry_decorator(max_attempts=5)
retry_llm_critical: Callable[..., Any] = create_retry_decorator(max_attempts=7)
