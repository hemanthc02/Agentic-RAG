"""Async exponential-backoff retry for provider calls.

Retries only the errors marked retryable in ``base.RETRYABLE`` (rate limits,
timeouts); auth/config/response errors fail fast. Backoff schedule and attempt
cap come from configuration (default 1, 2, 4 s ; 3 attempts).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from ai_service.base import RETRYABLE, LLMError

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    backoff_seconds: tuple[int, ...] = (1, 2, 4),
) -> T:
    """Call ``fn`` with retries on transient provider errors."""
    last: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except RETRYABLE as exc:  # transient → back off and retry
            last = exc
            if attempt == max_attempts:
                break
            delay = backoff_seconds[min(attempt - 1, len(backoff_seconds) - 1)]
            logger.warning("LLM call failed (attempt %d/%d): %s; retrying in %ss",
                           attempt, max_attempts, exc, delay)
            await asyncio.sleep(delay)
        except LLMError:
            raise  # non-retryable: fail fast
    assert last is not None
    raise last
