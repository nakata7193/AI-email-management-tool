"""Gmail API provider implementation using composition.

This module composes specialized components (authenticator, parser, fetcher, modifier)
instead of implementing everything in one class. This follows the Single Responsibility
Principle and makes the code more testable and maintainable.
"""

import logging
from typing import Dict, Iterator, List, Optional, Tuple

from providers.base import EmailProvider, Email
from providers.gmail_components.authenticator import GmailAuthenticator
from providers.gmail_components.parser import GmailMessageParser
from providers.gmail_components.fetcher import GmailFetcher
from providers.gmail_components.modifier import GmailModifier
from providers.gmail_components.analyzer import GmailAnalyzer

logger = logging.getLogger(__name__)


class GmailProvider(EmailProvider):
    """Gmail provider - composes specialized components.

    This class orchestrates the specialized components but delegates
    all actual work to them. This follows Composition Over Inheritance
    and Single Responsibility principles.
    """

    def __init__(self, config):
        """Initialize Gmail provider with configuration.

        Args:
            config: GmailConfig instance with credentials/token file paths
        """
        if not config:
            raise ValueError("GmailConfig is required")

        self._config = config
        self._connected = False

        # Compose specialized components
        self._authenticator = GmailAuthenticator(
            config.credentials_file,
            config.token_file
        )
        self._parser = GmailMessageParser()
        self._fetcher = GmailFetcher(self._parser)
        self._modifier = GmailModifier(self._parser)
        self._analyzer = GmailAnalyzer()

    def connect(self) -> None:
        """Establish connection to Gmail API."""
        try:
            # Authenticate
            creds = self._authenticator.get_credentials()

            # Initialize components with credentials
            self._fetcher.set_credentials(creds)
            self._modifier.set_credentials(creds)
            self._analyzer.set_credentials(creds)

            self._connected = True
            logger.info("Connected to Gmail API")

        except Exception as e:
            logger.error(f"Failed to connect to Gmail API: {e}")
            raise ConnectionError(f"Gmail API connection failed: {e}")

    def disconnect(self) -> None:
        """Close connection to Gmail API."""
        self._connected = False
        logger.info("Disconnected from Gmail API")

    def fetch_emails(
        self,
        limit: int = 100,
        unread_only: bool = False,
        max_workers: int = 10,
        since: Optional[str] = None
    ) -> List[Email]:
        """Fetch emails from Gmail.

        Args:
            limit: Maximum number of emails to fetch
            unread_only: Only fetch unread emails
            max_workers: Number of parallel workers
            since: Only fetch emails after this date (YYYY/MM/DD)

        Returns:
            List of Email objects
        """
        if not self._connected:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        return self._fetcher.fetch_emails(limit, unread_only, max_workers, since)

    def get_all_message_ids(
        self,
        limit: Optional[int] = None,
        unread_only: bool = False
    ) -> List[str]:
        """Get all message IDs from inbox.

        Args:
            limit: Maximum number of IDs (None = all)
            unread_only: Only get unread message IDs

        Returns:
            List of message IDs
        """
        if not self._connected:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        return self._fetcher.get_all_message_ids(limit, unread_only)

    def fetch_emails_by_ids(
        self,
        message_ids: List[str],
        max_workers: int = 10
    ) -> List[Email]:
        """Fetch full email content for given message IDs.

        Args:
            message_ids: List of Gmail message IDs
            max_workers: Number of parallel workers

        Returns:
            List of Email objects
        """
        if not self._connected:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        return self._fetcher.fetch_emails_by_ids(message_ids, max_workers)

    def search_gmail(self, query: str, limit: int = 100) -> List[Email]:
        """Search Gmail using Gmail's search syntax.

        Args:
            query: Gmail search query
            limit: Maximum results

        Returns:
            List of Email objects
        """
        if not self._connected:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        return self._fetcher.search_gmail(query, limit)

    def analyze_top_senders(self, limit: Optional[int] = None) -> dict:
        """Analyze Gmail to find top senders by email count.

        Args:
            limit: Number of recent emails to analyze (None = ALL)

        Returns:
            Dictionary mapping sender to email count
        """
        if not self._connected:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        return self._analyzer.analyze_top_senders(limit)

    def mark_as_read(self, email_id: str) -> bool:
        """Mark a Gmail message as read.

        Args:
            email_id: Gmail message ID

        Returns:
            True if successful
        """
        if not self._connected:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        return self._modifier.mark_as_read(email_id)

    def mark_as_unread(self, email_id: str) -> bool:
        """Mark a Gmail message as unread.

        Args:
            email_id: Gmail message ID

        Returns:
            True if successful
        """
        if not self._connected:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        return self._modifier.mark_as_unread(email_id)

    def delete_email(self, email_id: str, permanent: bool = False) -> bool:
        """Delete a Gmail message.

        Args:
            email_id: Gmail message ID
            permanent: If True, permanently delete. If False, move to trash.

        Returns:
            True if successful
        """
        if not self._connected:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        return self._modifier.delete_email(email_id, permanent)

    def untrash_email(self, email_id: str) -> bool:
        """Restore an email from trash.

        Args:
            email_id: Gmail message ID

        Returns:
            True if successful
        """
        if not self._connected:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        return self._modifier.untrash_email(email_id)

    def move_email(
        self,
        email_id: str,
        add_labels: Optional[List[str]] = None,
        remove_labels: Optional[List[str]] = None
    ) -> bool:
        """Move an email by modifying labels.

        Args:
            email_id: Gmail message ID
            add_labels: Labels to add
            remove_labels: Labels to remove

        Returns:
            True if successful
        """
        if not self._connected:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        return self._modifier.move_email(email_id, add_labels, remove_labels)

    def archive_email(self, email_id: str) -> bool:
        """Archive an email (remove from INBOX).

        Args:
            email_id: Gmail message ID

        Returns:
            True if successful
        """
        if not self._connected:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        return self._modifier.archive_email(email_id)

    def star_email(self, email_id: str, starred: bool = True) -> bool:
        """Star/unstar an email.

        Args:
            email_id: Gmail message ID
            starred: True to star, False to unstar

        Returns:
            True if successful
        """
        if not self._connected:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        return self._modifier.star_email(email_id, starred)

    def mark_as_spam(self, email_id: str) -> bool:
        """Mark an email as spam.

        Args:
            email_id: Gmail message ID

        Returns:
            True if successful
        """
        if not self._connected:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        return self._modifier.mark_as_spam(email_id)

    def list_labels(self) -> List[dict]:
        """List all Gmail labels.

        Returns:
            List of label dictionaries
        """
        if not self._connected:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        return self._modifier.list_labels()

    def ensure_labels(self, names: List[str]) -> Dict[str, str]:
        """Ensure all labels exist in Gmail, creating any that are missing.

        Args:
            names: Label names to ensure exist

        Returns:
            Dict mapping label name -> label ID
        """
        if not self._connected:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        return self._modifier.ensure_labels(names)

    def apply_category_label(
        self,
        email_id: str,
        label_id: str,
    ) -> bool:
        """Apply a category label to an email and remove it from INBOX.

        Args:
            email_id: Gmail message ID
            label_id: Gmail label ID to apply

        Returns:
            True if successful
        """
        if not self._connected:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        return self._modifier.move_email(
            email_id,
            add_labels=[label_id],
            remove_labels=['INBOX']
        )

    def get_email_by_id(self, email_id: str) -> Optional[Email]:
        """Retrieve a specific Gmail message by ID.

        Args:
            email_id: Gmail message ID

        Returns:
            Email object or None
        """
        if not self._connected:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        return self._modifier.get_email_by_id(email_id)
