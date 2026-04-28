"""AI client abstraction layer.

This module provides a protocol-based abstraction for AI clients,
decoupling business logic from specific AI provider implementations.
"""

import logging
from typing import Protocol, Optional
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class AIClient(Protocol):
    """Protocol for AI API clients.

    This abstraction allows business logic to remain independent of
    specific AI provider SDKs, making it easier to:
    - Test with mock clients
    - Switch AI providers
    - Implement rate limiting or caching at the client level
    """

    def complete(
        self,
        prompt: str,
        max_tokens: int = 500,
        model: Optional[str] = None
    ) -> str:
        """Generate a completion for the given prompt.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens in response
            model: Optional model override

        Returns:
            The completion text
        """
        ...


class ClaudeClient:
    """Anthropic Claude implementation of AIClient.

    This implementation uses the Anthropic SDK and adaptive thinking
    for all completions.
    """

    def __init__(self, api_key: str, default_model: str = "claude-opus-4-6"):
        """Initialize Claude client.

        Args:
            api_key: Anthropic API key
            default_model: Default model to use for completions
        """
        if not api_key:
            raise ValueError("Anthropic API key is required")

        self._client = Anthropic(api_key=api_key)
        self._default_model = default_model

    def complete(
        self,
        prompt: str,
        max_tokens: int = 500,
        model: Optional[str] = None
    ) -> str:
        """Generate a completion using Claude.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens in response
            model: Optional model override

        Returns:
            The completion text
        """
        try:
            response = self._client.messages.create(
                model=model or self._default_model,
                max_tokens=max_tokens,
                thinking={
                    "type": "adaptive"
                },
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Extract text from last content block
            if response.content:
                return response.content[-1].text

            return ""

        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            raise


class MockAIClient:
    """Mock AI client for testing.

    Returns predefined responses without making API calls.
    Useful for unit tests and development.
    """

    def __init__(self, responses: Optional[dict[str, str]] = None):
        """Initialize mock client.

        Args:
            responses: Dictionary mapping prompt substrings to responses
                      If None, returns a default response
        """
        self._responses = responses or {}
        self._default_response = "Mock AI response"
        self._call_count = 0

    def complete(
        self,
        prompt: str,
        max_tokens: int = 500,
        model: Optional[str] = None
    ) -> str:
        """Return a predefined mock response.

        Args:
            prompt: The input prompt
            max_tokens: Ignored in mock
            model: Ignored in mock

        Returns:
            Mock response text
        """
        self._call_count += 1

        # Check if prompt matches any configured responses
        for key, response in self._responses.items():
            if key.lower() in prompt.lower():
                return response

        return self._default_response

    @property
    def call_count(self) -> int:
        """Get number of times complete() was called."""
        return self._call_count
