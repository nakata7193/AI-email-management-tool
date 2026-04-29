"""Dependency injection container.

This module centralizes object creation and dependency management,
removing this responsibility from the CLI layer.
"""

import logging
from typing import Optional
from pathlib import Path

from providers.base import EmailProvider
from providers.gmail import GmailProvider
from providers.imap import IMAPProvider
from storage.cache import EmailCache
from services.email_service import EmailService
from ai.client import ClaudeClient, AIClient
from ai.categorizer import EmailCategorizer
from ai.summarizer import EmailSummarizer
from ai.search import EmailSearcher

logger = logging.getLogger(__name__)


class ServiceContainer:
    """Dependency injection container for email management services.

    This class follows the Single Responsibility Principle by focusing
    solely on object creation and lifecycle management. It uses lazy
    initialization to only create objects when needed.

    Usage:
        container = ServiceContainer(config)
        service = container.email_service
        provider = container.get_provider('gmail')
    """

    def __init__(self, config: dict):
        """Initialize container with configuration.

        Args:
            config: Configuration dictionary with provider/AI settings
        """
        self._config = config
        self._cache: Optional[EmailCache] = None
        self._email_service: Optional[EmailService] = None
        self._ai_client: Optional[AIClient] = None
        self._categorizer: Optional[EmailCategorizer] = None
        self._summarizer: Optional[EmailSummarizer] = None
        self._searcher: Optional[EmailSearcher] = None

    @property
    def cache(self) -> EmailCache:
        """Get or create email cache instance.

        Returns:
            EmailCache instance (singleton per container)
        """
        if not self._cache:
            db_path = self._config['database'].path
            self._cache = EmailCache(db_path)
            logger.debug(f"Created EmailCache with database: {db_path}")
        return self._cache

    @property
    def email_service(self) -> EmailService:
        """Get or create email service instance.

        Returns:
            EmailService instance (singleton per container)
        """
        if not self._email_service:
            self._email_service = EmailService(self.cache)
            logger.debug("Created EmailService")
        return self._email_service

    @property
    def ai_client(self) -> AIClient:
        """Get or create AI client instance.

        Returns:
            AIClient instance (singleton per container)
        """
        if not self._ai_client:
            claude_config = self._config['claude']
            self._ai_client = ClaudeClient(
                api_key=claude_config.api_key,
                base_url=claude_config.base_url
            )
            logger.debug("Created ClaudeClient")
        return self._ai_client

    @property
    def categorizer(self) -> EmailCategorizer:
        """Get or create email categorizer instance.

        Returns:
            EmailCategorizer instance (singleton per container)
        """
        if not self._categorizer:
            self._categorizer = EmailCategorizer(self.ai_client)
            logger.debug("Created EmailCategorizer")
        return self._categorizer

    @property
    def summarizer(self) -> EmailSummarizer:
        """Get or create email summarizer instance.

        Returns:
            EmailSummarizer instance (singleton per container)
        """
        if not self._summarizer:
            self._summarizer = EmailSummarizer(self.ai_client)
            logger.debug("Created EmailSummarizer")
        return self._summarizer

    @property
    def searcher(self) -> EmailSearcher:
        """Get or create email searcher instance.

        Returns:
            EmailSearcher instance (singleton per container)
        """
        if not self._searcher:
            self._searcher = EmailSearcher(self.ai_client)
            logger.debug("Created EmailSearcher")
        return self._searcher

    def get_provider(self, provider_type: str) -> EmailProvider:
        """Create a provider instance.

        Note: Providers are NOT cached because they maintain connection state
        and should be created/connected/disconnected per operation.

        Args:
            provider_type: Provider type ('gmail' or 'imap')

        Returns:
            EmailProvider instance

        Raises:
            ValueError: If provider_type is not recognized
        """
        if provider_type == 'gmail':
            provider = GmailProvider(self._config['gmail'])
            logger.debug("Created GmailProvider")
            return provider
        elif provider_type == 'imap':
            provider = IMAPProvider(self._config['imap'])
            logger.debug("Created IMAPProvider")
            return provider
        else:
            raise ValueError(
                f"Unknown provider: {provider_type}. "
                f"Must be 'gmail' or 'imap'"
            )

    def close(self) -> None:
        """Close all resources managed by this container.

        Should be called when done with the container to ensure
        proper cleanup of database connections, etc.
        """
        if self._cache:
            self._cache.close()
            logger.debug("Closed EmailCache")

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()
