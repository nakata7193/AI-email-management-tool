"""Provider-agnostic retry utility.

Separates retry policy (when to retry, how long to wait) from the code that
makes API calls. Callers pass a callable and decide which exceptions are
retryable and what the wait schedule looks like.

Usage::

    result = with_retry(
        lambda: service.users().messages().get(...).execute(),
        max_retries=5,
        retryable=(ConnectionError, OSError),
        backoff_fn=lambda attempt: min(30 * (2 ** attempt), 300),
        logger=logger,
        label="fetch message abc123",
    )
"""

import logging
import time
from typing import Callable, Optional, Tuple, TypeVar

T = TypeVar('T')

_default_logger = logging.getLogger(__name__)


def with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int,
    retryable: Tuple[type, ...],
    backoff_fn: Callable[[int], float],
    logger: Optional[logging.Logger] = None,
    label: str = "operation",
) -> T:
    """Call fn, retrying on retryable exceptions with caller-supplied backoff.

    Args:
        fn: Zero-argument callable to invoke.
        max_retries: Maximum number of retry attempts (not counting the first try).
        retryable: Tuple of exception types that should trigger a retry.
        backoff_fn: Called with the attempt number (1-based) and returns seconds
                    to sleep before that attempt.
        logger: Logger to use for warnings/errors. Defaults to module logger.
        label: Human-readable description used in log messages.

    Returns:
        The return value of fn on success.

    Raises:
        The last retryable exception if all retries are exhausted.
        Any non-retryable exception immediately.
    """
    log = logger or _default_logger
    last_exc: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            return fn()
        except retryable as e:
            last_exc = e
            if attempt < max_retries:
                wait = backoff_fn(attempt + 1)
                log.warning(
                    f"Retryable error during {label} "
                    f"(attempt {attempt + 1}/{max_retries}): {e} — "
                    f"retrying in {wait:.0f}s"
                )
                time.sleep(wait)
            else:
                log.error(
                    f"Failed {label} after {max_retries} retries: {e}"
                )

    raise last_exc
