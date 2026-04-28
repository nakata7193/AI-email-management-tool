"""Email service layer - business logic separated from CLI and storage concerns."""

import logging
from typing import List, Optional, Dict, Any, Iterator
from dataclasses import dataclass
from datetime import datetime

from providers.base import EmailProvider, Email
from storage.cache import EmailCache
from ai.categorizer import EmailCategorizer
from ai.summarizer import EmailSummarizer
from ai.search import EmailSearcher


logger = logging.getLogger(__name__)

# Valid categories for validation
VALID_CATEGORIES = {'urgent', 'important', 'newsletter', 'receipts', 'social', 'can_wait'}

# Valid providers for validation
VALID_PROVIDERS = {'gmail', 'imap'}


@dataclass
class ProgressUpdate:
    """Progress update for batch operations."""
    batch_num: int
    total_stored: int
    total_requested: int
    db_count: int


@dataclass
class FetchResult:
    """Result of email fetch operation."""
    total_stored: int
    batches: int
    final_db_count: int


@dataclass
class CategorizeResult:
    """Result of categorization operation."""
    processed: int
    successful: int
    failed: int


@dataclass
class SearchResult:
    """Result of search operation."""
    results: List[Dict[str, Any]]
    count: int


@dataclass
class SummaryResult:
    """Result of email summary operation."""
    summary: str
    action_items: Optional[str]
    from_cache: bool


class EmailService:
    """
    Business logic for email operations.

    Responsibilities:
    - Orchestrate email fetching with batching and progress tracking
    - Coordinate categorization workflows
    - Handle email search with AI parsing and ranking
    - Manage email summaries with caching

    This layer separates business logic from CLI concerns (argument parsing,
    formatting) and storage concerns (SQL queries, transactions).
    """

    def __init__(self, cache: EmailCache) -> None:
        self._cache = cache
        self._logger = logger

    def fetch_and_store_emails(
        self,
        provider: EmailProvider,
        provider_name: str,
        limit: int,
        batch_size: int,
        unread_only: bool
    ) -> Iterator[ProgressUpdate]:
        """
        Fetch emails in batches and store to cache.

        Yields progress updates after each batch for CLI display.

        Args:
            provider: Email provider instance (Gmail/IMAP)
            provider_name: Provider name for storage ('gmail'/'imap')
            limit: Maximum emails to fetch
            batch_size: Emails per batch
            unread_only: Only fetch unread emails

        Yields:
            ProgressUpdate after each batch completes
        """
        total_stored = 0
        batch_num = 0
        remaining = limit

        while remaining > 0:
            fetch_size = min(batch_size, remaining)
            emails = provider.fetch_emails(limit=fetch_size, unread_only=unread_only)

            if not emails:
                self._logger.info("No more emails to fetch")
                break

            # Store batch
            for email in emails:
                self._cache.store_email(email, provider_name)
                total_stored += 1

            batch_num += 1
            remaining -= len(emails)

            # Get current DB count for verification
            db_count = self._cache.get_count()

            yield ProgressUpdate(
                batch_num=batch_num,
                total_stored=total_stored,
                total_requested=limit,
                db_count=db_count
            )

            # If we got fewer emails than requested, we've reached the end
            if len(emails) < fetch_size:
                self._logger.info(f"Reached end of mailbox (fetched {len(emails)} < requested {fetch_size})")
                break

        # Final count
        final_count = self._cache.get_count()
        self._logger.info(f"Fetch complete: {total_stored} emails stored, {final_count} total in DB")

    def categorize_uncategorized_emails(
        self,
        categorizer: EmailCategorizer,
        limit: int
    ) -> Iterator[tuple[int, int, Dict[str, Any], str]]:
        """
        Categorize emails without categories.

        Yields progress updates for each email processed.

        Args:
            categorizer: Email categorizer instance
            limit: Maximum emails to categorize

        Yields:
            Tuple of (current_index, total_count, email_data, category)
        """
        uncategorized = self._cache.get_uncategorized_emails(limit=limit)

        if not uncategorized:
            return

        total = len(uncategorized)

        for i, email_obj in enumerate(uncategorized, 1):
            try:
                result = categorizer.categorize(email_obj)

                self._cache.update_category(
                    email_obj.id,
                    result['category'],
                    result['reasoning']
                )

                yield (i, total, {
                    'id': email_obj.id,
                    'subject': email_obj.subject
                }, result['category'])

            except Exception as e:
                self._logger.error(f"Failed to categorize email {email_obj.id}: {e}")
                yield (i, total, {
                    'id': email_obj.id,
                    'subject': email_obj.subject
                }, 'ERROR')

    def search_emails(
        self,
        searcher: EmailSearcher,
        query: str,
        limit: int
    ) -> SearchResult:
        """
        Search emails using natural language query.

        Args:
            searcher: Email searcher instance
            query: Natural language search query
            limit: Maximum results to return

        Returns:
            SearchResult with ranked results
        """
        # Parse natural language query
        search_params = searcher.parse_search_query(query)
        self._logger.info("Search parameters extracted from query")

        # Build and execute SQL query
        sql_query, params = searcher.build_sql_query(search_params)
        results = self._cache.execute_search_query(sql_query, params)

        if not results:
            return SearchResult(results=[], count=0)

        # Rank results if multiple found
        if len(results) > 1:
            self._logger.info("Ranking results by relevance")
            results = searcher.rank_results(results, query)

        # Apply limit
        results = results[:limit]

        return SearchResult(results=results, count=len(results))

    def get_email_summary(
        self,
        summarizer: EmailSummarizer,
        email_id: str
    ) -> Optional[SummaryResult]:
        """
        Get or generate email summary.

        Checks cache first, generates with AI if not cached.

        Args:
            summarizer: Email summarizer instance
            email_id: Email ID to summarize

        Returns:
            SummaryResult or None if email not found
        """
        # Get email from cache
        email_dict = self._cache.get_email_by_id(email_id)

        if not email_dict:
            return None

        # Check if summary exists in cache
        if email_dict.get('summary'):
            return SummaryResult(
                summary=email_dict['summary'],
                action_items=email_dict.get('action_items'),
                from_cache=True
            )

        # Generate new summary
        email_obj = self._dict_to_email(email_dict)
        result = summarizer.summarize(email_obj)

        # Cache the summary
        self._cache.update_summary(
            email_id,
            result['summary'],
            result.get('action_items')
        )

        return SummaryResult(
            summary=result['summary'],
            action_items=result.get('action_items'),
            from_cache=False
        )

    def get_emails(
        self,
        limit: int = 100,
        unread_only: bool = False,
        category: Optional[str] = None,
        provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get emails with filters and validation.

        Args:
            limit: Maximum emails to return (1-1000)
            unread_only: Only return unread emails
            category: Filter by category (must be valid category)
            provider: Filter by provider (must be valid provider)

        Returns:
            List of email dictionaries

        Raises:
            ValueError: If validation fails
        """
        # Validate inputs
        if limit < 1:
            raise ValueError(f"limit must be positive, got {limit}")

        if limit > 1000:
            self._logger.warning(f"Large limit requested: {limit}, clamping to 1000")
            limit = 1000

        if category and category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category: {category}. "
                f"Must be one of: {', '.join(VALID_CATEGORIES)}"
            )

        if provider and provider not in VALID_PROVIDERS:
            raise ValueError(
                f"Invalid provider: {provider}. "
                f"Must be one of: {', '.join(VALID_PROVIDERS)}"
            )

        return self._cache.get_emails(
            limit=limit,
            unread_only=unread_only,
            category=category,
            provider=provider
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Get email statistics from cache."""
        return self._cache.get_statistics()

    def get_uncategorized_count(self, limit: int = 100) -> int:
        """
        Get count of uncategorized emails.

        Args:
            limit: Maximum emails to check

        Returns:
            Number of uncategorized emails
        """
        if limit < 1:
            raise ValueError(f"limit must be positive, got {limit}")

        uncategorized = self._cache.get_uncategorized_emails(limit=limit)
        return len(uncategorized)

    def clean_old_emails(self, days: Optional[int] = None) -> int:
        """
        Clean emails older than specified days.

        Args:
            days: Number of days to keep (default from config)

        Returns:
            Number of emails deleted
        """
        return self._cache.clean_old_emails(days)

    def _dict_to_email(self, data: dict) -> Email:
        """Convert dictionary to Email object using centralized logic."""
        return Email.from_dict(data)
