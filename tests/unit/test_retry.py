"""Unit tests for providers.retry.with_retry.

Tests cover:
- Succeeds on first attempt (no retries needed)
- Retries on retryable exceptions and eventually succeeds
- Raises after exhausting all retries
- Non-retryable exceptions propagate immediately
- Backoff function is called with correct attempt numbers
- Sleep is called with values returned by backoff_fn

Run from project root:
    python -m unittest tests/unit/test_retry.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
from unittest.mock import MagicMock, patch, call

from providers.retry import with_retry


class RetryableError(Exception):
    pass


class OtherError(Exception):
    pass


def _no_backoff(_attempt: int) -> float:
    return 0.0


class TestWithRetrySuccess(unittest.TestCase):

    def test_returns_value_on_first_try(self):
        fn = MagicMock(return_value="ok")
        result = with_retry(fn, max_retries=3, retryable=(RetryableError,), backoff_fn=_no_backoff)
        self.assertEqual(result, "ok")
        fn.assert_called_once()

    def test_returns_value_after_one_failure(self):
        fn = MagicMock(side_effect=[RetryableError("transient"), "ok"])
        result = with_retry(fn, max_retries=3, retryable=(RetryableError,), backoff_fn=_no_backoff)
        self.assertEqual(result, "ok")
        self.assertEqual(fn.call_count, 2)

    def test_returns_value_on_last_retry(self):
        # Fails max_retries times then succeeds
        fn = MagicMock(side_effect=[RetryableError("x")] * 3 + ["final"])
        result = with_retry(fn, max_retries=3, retryable=(RetryableError,), backoff_fn=_no_backoff)
        self.assertEqual(result, "final")
        self.assertEqual(fn.call_count, 4)


class TestWithRetryExhausted(unittest.TestCase):

    def test_raises_after_all_retries_exhausted(self):
        fn = MagicMock(side_effect=RetryableError("persistent"))
        with self.assertRaises(RetryableError):
            with_retry(fn, max_retries=3, retryable=(RetryableError,), backoff_fn=_no_backoff)

    def test_call_count_equals_one_plus_max_retries(self):
        fn = MagicMock(side_effect=RetryableError("x"))
        try:
            with_retry(fn, max_retries=4, retryable=(RetryableError,), backoff_fn=_no_backoff)
        except RetryableError:
            pass
        self.assertEqual(fn.call_count, 5)  # 1 initial + 4 retries

    def test_raises_last_exception_instance(self):
        errors = [RetryableError(f"attempt {i}") for i in range(3)]
        fn = MagicMock(side_effect=errors)
        with self.assertRaises(RetryableError) as ctx:
            with_retry(fn, max_retries=2, retryable=(RetryableError,), backoff_fn=_no_backoff)
        self.assertEqual(str(ctx.exception), "attempt 2")


class TestWithRetryNonRetryable(unittest.TestCase):

    def test_non_retryable_exception_propagates_immediately(self):
        fn = MagicMock(side_effect=OtherError("fatal"))
        with self.assertRaises(OtherError):
            with_retry(fn, max_retries=5, retryable=(RetryableError,), backoff_fn=_no_backoff)
        fn.assert_called_once()

    def test_no_sleep_on_non_retryable(self):
        fn = MagicMock(side_effect=OtherError("fatal"))
        with patch("providers.retry.time.sleep") as mock_sleep:
            try:
                with_retry(fn, max_retries=3, retryable=(RetryableError,), backoff_fn=_no_backoff)
            except OtherError:
                pass
        mock_sleep.assert_not_called()


class TestWithRetryBackoff(unittest.TestCase):

    def test_backoff_fn_called_with_sequential_attempt_numbers(self):
        backoff = MagicMock(return_value=0.0)
        fn = MagicMock(side_effect=[RetryableError("x"), RetryableError("x"), "ok"])

        with patch("providers.retry.time.sleep"):
            with_retry(fn, max_retries=3, retryable=(RetryableError,), backoff_fn=backoff)

        # Two failures → backoff called for attempt 1 and 2
        backoff.assert_has_calls([call(1), call(2)])
        self.assertEqual(backoff.call_count, 2)

    def test_sleep_called_with_backoff_fn_return_value(self):
        backoff = MagicMock(side_effect=[10.0, 20.0])
        fn = MagicMock(side_effect=[RetryableError("x"), RetryableError("x"), "ok"])

        with patch("providers.retry.time.sleep") as mock_sleep:
            with_retry(fn, max_retries=3, retryable=(RetryableError,), backoff_fn=backoff)

        mock_sleep.assert_has_calls([call(10.0), call(20.0)])

    def test_no_sleep_after_final_failure(self):
        """Sleep should NOT be called after the last failed attempt."""
        calls = []
        backoff = MagicMock(side_effect=lambda attempt: calls.append(attempt) or 0.0)
        fn = MagicMock(side_effect=RetryableError("x"))

        with patch("providers.retry.time.sleep"):
            try:
                with_retry(fn, max_retries=2, retryable=(RetryableError,), backoff_fn=backoff)
            except RetryableError:
                pass

        # max_retries=2: sleep called for attempts 1 and 2, NOT after attempt 3
        self.assertEqual(calls, [1, 2])


class TestWithRetryMultipleRetryableTypes(unittest.TestCase):

    def test_retries_on_any_type_in_tuple(self):
        class NetworkError(Exception):
            pass

        class TimeoutError(Exception):
            pass

        fn = MagicMock(side_effect=[NetworkError("net"), TimeoutError("timeout"), "ok"])

        with patch("providers.retry.time.sleep"):
            result = with_retry(
                fn,
                max_retries=3,
                retryable=(NetworkError, TimeoutError),
                backoff_fn=_no_backoff,
            )

        self.assertEqual(result, "ok")
        self.assertEqual(fn.call_count, 3)


if __name__ == "__main__":
    unittest.main()
