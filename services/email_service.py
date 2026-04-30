"""Email service layer - business logic separated from CLI and storage concerns."""

import logging
from typing import List, Optional, Dict, Any, Iterator
from dataclasses import dataclass
from datetime import datetime

from providers.base import EmailProvider, Email
from storage.cache import EmailCache
from ai.categorizer import EmailCategorizer, BATCH_SIZE
from ai.summarizer import EmailSummarizer
from ai.search import EmailSearcher


logger = logging.getLogger(__name__)

# Valid providers for validation
VALID_PROVIDERS = {'gmail', 'imap'}


@dataclass
class ProgressUpdate:
    """Progress update for batch fetch operations."""
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


# --- Progress events for generator-based operations ---

@dataclass
class ProgressEvent:
    """Base class for per-item progress events from generator operations.

    All generator-based service methods yield subclasses of this type,
    giving callers a stable interface for the common fields (index, total)
    while concrete subclasses carry operation-specific fields.
    """
    index: int
    total: int


@dataclass
class CategorizeProgress(ProgressEvent):
    """Yielded once per email during categorize_emails()."""
    subject: str
    category: str


@dataclass
class OrganizeProgress(ProgressEvent):
    """Yielded once per email during organize_emails()."""
    subject: str
    category: str
    success: bool


@dataclass
class DeleteProgress(ProgressEvent):
    """Yielded once per email during delete_emails_by_category()."""
    subject: str
    success: bool


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

    def __init__(self, cache: EmailCache, categories: Dict[str, Any]) -> None:
        self._cache = cache
        self._categories = categories
        self._logger = logger

    def fetch_and_store_emails(
        self,
        provider: EmailProvider,
        provider_name: str,
        limit: int,
        batch_size: int,
        unread_only: bool,
        since: Optional[str] = None
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
            since: Only fetch emails after this date (YYYY/MM/DD, Gmail only)

        Yields:
            ProgressUpdate after each batch completes
        """
        total_stored = 0
        batch_num = 0
        remaining = limit

        while remaining > 0:
            fetch_size = min(batch_size, remaining)
            fetch_kwargs = dict(limit=fetch_size, unread_only=unread_only)
            if since and hasattr(provider, '_fetcher'):
                fetch_kwargs['since'] = since
            emails = provider.fetch_emails(**fetch_kwargs)

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

    def categorize_emails(
        self,
        categorizer: EmailCategorizer,
        limit: int,
        recategorize: Optional[str] = None
    ) -> Iterator[CategorizeProgress]:
        """
        Categorize emails in batches of 100 per API call.

        By default categorizes only uncategorized emails.
        Pass recategorize='all' to redo all emails, or recategorize='newsletter'
        to redo only emails currently in that category.

        Args:
            categorizer: Email categorizer instance
            limit: Maximum emails to categorize
            recategorize: None = uncategorized only, 'all' = everything,
                          or a category name to redo that category

        Yields:
            CategorizeProgress after each email is processed
        """
        if recategorize is None:
            emails = self._cache.get_uncategorized_emails(limit=limit)
        elif recategorize == 'all':
            email_dicts = self._cache.get_emails(limit=limit)
            emails = [Email.from_dict(e) for e in email_dicts]
        else:
            email_dicts = self._cache.get_emails(limit=limit, category=recategorize)
            emails = [Email.from_dict(e) for e in email_dicts]

        if not emails:
            return

        total = len(emails)
        processed = 0

        for batch_start in range(0, total, BATCH_SIZE):
            batch = emails[batch_start:batch_start + BATCH_SIZE]

            try:
                batch_results = categorizer.batch_categorize(batch)
            except Exception as e:
                self._logger.error(f"Batch failed at offset {batch_start}: {e}")
                batch_results = {
                    email.id: {'category': 'other', 'reasoning': str(e)}
                    for email in batch
                }

            for email_obj in batch:
                processed += 1
                result = batch_results.get(email_obj.id, {'category': 'other', 'reasoning': ''})
                category = result['category']

                try:
                    self._cache.update_category(
                        email_obj.id,
                        category,
                        result.get('reasoning', '')
                    )
                except Exception as e:
                    self._logger.error(f"Failed to save category for {email_obj.id}: {e}")
                    category = 'ERROR'

                yield CategorizeProgress(
                    index=processed,
                    total=total,
                    subject=email_obj.subject,
                    category=category,
                )

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
        email_obj = Email.from_dict(email_dict)
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

        if category and category not in self._categories:
            raise ValueError(
                f"Invalid category: {category}. "
                f"Must be one of: {', '.join(self._categories)}"
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

    def organize_emails(
        self,
        gmail,
        category: Optional[str] = None,
        limit: int = 500,
        dry_run: bool = False
    ) -> Iterator[OrganizeProgress]:
        """
        Apply AI category labels to Gmail emails and move them out of inbox.

        Reads categorized emails from local DB (provider=gmail), ensures Gmail labels
        exist for each category, then applies the label and removes INBOX from each email.

        Args:
            gmail: Connected GmailProvider instance
            category: Only process this category (None = all categories)
            limit: Maximum number of emails to process
            dry_run: If True, yield progress without making Gmail API calls

        Yields:
            OrganizeProgress after each email is processed
        """
        emails = self._cache.get_emails(limit=limit, category=category, provider='gmail')
        # Only process emails that actually have a category set
        emails = [e for e in emails if e.get('category')]

        if not emails:
            return

        # Build label map upfront: category_key -> Gmail label ID
        # Gmail label names are derived from category keys (e.g. concert_tickets -> Concert Tickets)
        from config import category_to_folder
        categories_needed = (
            [category] if category
            else list({e['category'] for e in emails})
        )
        folder_names = {cat: category_to_folder(cat) for cat in categories_needed}

        if not dry_run:
            label_map = gmail.ensure_labels(list(folder_names.values()))
            # Remap: category_key -> label_id (via folder name)
            label_map = {cat: label_map[folder] for cat, folder in folder_names.items() if folder in label_map}
        else:
            label_map = {cat: f'<dry-run-id:{cat}>' for cat in categories_needed}

        total = len(emails)

        for i, email in enumerate(emails, 1):
            cat = email['category']
            label_id = label_map.get(cat)

            if not label_id:
                self._logger.warning(f"No label ID for category '{cat}', skipping email {email['id']}")
                yield OrganizeProgress(index=i, total=total, subject=email.get('subject', ''), category=cat, success=False)
                continue

            if dry_run:
                success = True
            else:
                success = gmail.apply_category_label(email['id'], label_id)

            yield OrganizeProgress(index=i, total=total, subject=email.get('subject', ''), category=cat, success=success)

    def delete_emails_by_category(
        self,
        gmail,
        category: str,
        limit: int = 500,
        permanent: bool = False,
        dry_run: bool = False
    ) -> Iterator[DeleteProgress]:
        """Delete all Gmail emails in a given category.

        Loads emails from the local DB filtered by category, then calls the
        Gmail API to trash (or permanently delete) each one.

        Args:
            gmail: Connected GmailProvider instance
            category: Category key to delete (e.g. 'promotional')
            limit: Maximum number of emails to delete
            permanent: If True, permanently delete. If False (default), move to trash.
            dry_run: If True, yield progress without making Gmail API calls

        Yields:
            DeleteProgress after each email is processed
        """
        emails = self._cache.get_emails(limit=limit, category=category, provider='gmail')
        emails = [e for e in emails if e.get('category') == category]

        if not emails:
            return

        total = len(emails)

        for i, email in enumerate(emails, 1):
            if dry_run:
                success = True
            else:
                success = gmail.delete_email(email['id'], permanent=permanent)

            yield DeleteProgress(index=i, total=total, subject=email.get('subject', ''), success=success)

    def clean_old_emails(self, days: Optional[int] = None) -> int:
        """
        Clean emails older than specified days.

        Args:
            days: Number of days to keep (default from config)

        Returns:
            Number of emails deleted
        """
        return self._cache.clean_old_emails(days)
