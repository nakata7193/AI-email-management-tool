"""Gmail email fetcher with parallel processing and retry logic."""

import logging
from typing import List, Optional
from socket import gaierror
from urllib.error import URLError
from http.client import RemoteDisconnected
from concurrent.futures import ThreadPoolExecutor, as_completed

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from providers.base import Email
from providers.gmail_components.parser import GmailMessageParser
from providers.retry import with_retry

logger = logging.getLogger(__name__)

# Exception types that indicate a transient network problem worth retrying.
_NETWORK_ERRORS = (ConnectionError, gaierror, URLError, RemoteDisconnected, OSError)

# Backoff schedules (both capped at 5 minutes).
def _network_backoff(attempt: int) -> float:
    """Exponential backoff for network errors: 60s, 120s, 240s, 300s, …"""
    return min(30 * (2 ** attempt), 300)

def _rate_limit_backoff(attempt: int) -> float:
    """Linear backoff for rate-limit errors: 60s, 120s, 180s, 240s, 300s."""
    return min(60 * attempt, 300)


class GmailFetcher:
    """Fetches emails from Gmail with pagination and parallelization.

    Single Responsibility: Email fetching logic only.
    Includes retry logic and parallel processing for performance.
    """

    def __init__(self, parser: Optional[GmailMessageParser] = None):
        """Initialize fetcher.

        Args:
            parser: Message parser (optional, creates default if None)
        """
        self._parser = parser or GmailMessageParser()
        self._service = None
        self._creds = None

    def set_credentials(self, creds: Credentials) -> None:
        """Set Gmail API credentials.

        Args:
            creds: OAuth2 credentials
        """
        self._creds = creds
        self._service = build('gmail', 'v1', credentials=creds)
        logger.debug("Gmail service initialized")

    def _get_thread_safe_service(self):
        """Create a new Gmail service instance for thread-safe operations.

        Returns:
            Gmail API service
        """
        if not self._creds:
            raise RuntimeError("Credentials not set. Call set_credentials() first.")
        return build('gmail', 'v1', credentials=self._creds)

    def get_all_message_ids(
        self,
        limit: Optional[int] = None,
        unread_only: bool = False,
        since: Optional[str] = None
    ) -> List[str]:
        """Get message IDs from inbox (lightweight, no content).

        Args:
            limit: Maximum number of IDs to return (None = all)
            unread_only: Only get unread message IDs
            since: Only fetch emails after this date (YYYY/MM/DD format for Gmail query)

        Returns:
            List of message IDs
        """
        if not self._service:
            raise RuntimeError("Service not initialized. Call set_credentials() first.")

        parts = []
        if unread_only:
            parts.append('is:unread')
        if since:
            parts.append(f'after:{since}')
        query = ' '.join(parts)
        all_ids = []
        page_token = None

        while True:
            batch_size = 500  # Gmail API max per request
            if limit and len(all_ids) + batch_size > limit:
                batch_size = limit - len(all_ids)

            results = self._service.users().messages().list(
                userId='me',
                labelIds=['INBOX'],
                q=query,
                maxResults=batch_size,
                pageToken=page_token
            ).execute()

            messages = results.get('messages', [])
            all_ids.extend([msg['id'] for msg in messages])

            page_token = results.get('nextPageToken')

            if len(all_ids) % 5000 == 0 and len(all_ids) > 0:
                logger.info(f"Listed {len(all_ids)} message IDs...")

            if not page_token or not messages:
                break
            if limit and len(all_ids) >= limit:
                break

        logger.info(f"Total message IDs found: {len(all_ids)}")
        return all_ids

    def fetch_single_email(self, message_id: str) -> Optional[Email]:
        """Fetch a single email with retry logic.

        Thread-safe — creates its own service instance.

        Retries on transient network errors (exponential backoff) and Gmail
        rate-limit responses (linear backoff). Returns None for permanent
        failures (non-retryable HTTP errors, unknown exceptions).

        Args:
            message_id: Gmail message ID

        Returns:
            Email object or None if the fetch ultimately failed
        """
        service = self._get_thread_safe_service()

        def _fetch():
            return service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

        # --- network errors: exponential backoff ---
        try:
            raw = with_retry(
                _fetch,
                max_retries=5,
                retryable=_NETWORK_ERRORS,
                backoff_fn=_network_backoff,
                logger=logger,
                label=f"fetch message {message_id}",
            )
            return self._parser.parse(raw)

        except _NETWORK_ERRORS as e:
            logger.error(f"Network failure for message {message_id} after all retries: {e}")
            return None

        except HttpError as e:
            if e.resp.status in (429, 503):
                # --- rate-limit errors: linear backoff ---
                try:
                    raw = with_retry(
                        _fetch,
                        max_retries=5,
                        retryable=(HttpError,),
                        backoff_fn=_rate_limit_backoff,
                        logger=logger,
                        label=f"fetch message {message_id} (rate-limited)",
                    )
                    return self._parser.parse(raw)
                except HttpError as e2:
                    logger.error(f"Rate-limit failure for message {message_id} after all retries: {e2}")
                    return None
            else:
                logger.warning(f"HTTP error fetching message {message_id}: {e}")
                return None

        except Exception as e:
            logger.warning(f"Failed to fetch message {message_id}: {e}")
            return None

    def fetch_emails_by_ids(
        self,
        message_ids: List[str],
        max_workers: int = 10
    ) -> List[Email]:
        """Fetch full email content for given message IDs in parallel.

        Args:
            message_ids: List of Gmail message IDs to fetch
            max_workers: Number of parallel workers

        Returns:
            List of Email objects
        """
        if not message_ids:
            return []

        logger.info(
            f"Fetching {len(message_ids)} emails with {max_workers} parallel workers..."
        )

        emails = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_id = {
                executor.submit(self.fetch_single_email, msg_id): msg_id
                for msg_id in message_ids
            }

            completed = 0
            for future in as_completed(future_to_id):
                completed += 1

                if completed % 100 == 0:
                    logger.info(f"Progress: {completed}/{len(message_ids)} emails fetched...")

                try:
                    email_obj = future.result()
                    if email_obj:
                        emails.append(email_obj)
                except Exception as e:
                    msg_id = future_to_id[future]
                    logger.error(f"Exception fetching message {msg_id}: {e}")

        logger.info(f"Fetched {len(emails)} emails")
        return emails

    def fetch_emails(
        self,
        limit: int = 100,
        unread_only: bool = False,
        max_workers: int = 10,
        since: Optional[str] = None
    ) -> List[Email]:
        """Fetch emails from Gmail with parallel processing.

        Args:
            limit: Maximum number of emails to fetch
            unread_only: Only fetch unread emails
            max_workers: Number of parallel workers (default: 10)
            since: Only fetch emails after this date (YYYY/MM/DD)

        Returns:
            List of Email objects
        """
        if not self._service:
            raise RuntimeError("Service not initialized. Call set_credentials() first.")

        try:
            # Build query
            parts = []
            if unread_only:
                parts.append('is:unread')
            if since:
                parts.append(f'after:{since}')
            query = ' '.join(parts)

            # Fetch message IDs using pagination
            all_messages = []
            page_token = None

            while len(all_messages) < limit:
                # Gmail API maxResults cap is 500 per request
                batch_size = min(500, limit - len(all_messages))

                results = self._service.users().messages().list(
                    userId='me',
                    labelIds=['INBOX'],
                    q=query,
                    maxResults=batch_size,
                    pageToken=page_token
                ).execute()

                messages = results.get('messages', [])
                all_messages.extend(messages)

                # Update page token for next iteration
                page_token = results.get('nextPageToken')

                # If no more messages or no next page, stop
                if not page_token or not messages:
                    break

                if len(all_messages) >= limit:
                    break

                # Log progress for large fetches
                if len(all_messages) % 1000 == 0:
                    logger.info(f"Listed {len(all_messages)} message IDs so far...")

            if not all_messages:
                logger.info("No messages found")
                return []

            logger.info(
                f"Fetching {len(all_messages)} emails with {max_workers} parallel workers..."
            )

            # Fetch emails in parallel
            message_ids = [msg['id'] for msg in all_messages]
            return self.fetch_emails_by_ids(message_ids, max_workers)

        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return []

    def search_gmail(self, query: str, limit: int = 100) -> List[Email]:
        """Search Gmail directly using Gmail's search syntax.

        Args:
            query: Gmail search query
            limit: Maximum number of results

        Returns:
            List of Email objects matching the query
        """
        if not self._service:
            raise RuntimeError("Service not initialized. Call set_credentials() first.")

        try:
            results = self._service.users().messages().list(
                userId='me',
                q=query,
                maxResults=limit
            ).execute()

            messages = results.get('messages', [])

            if not messages:
                logger.info(f"No messages found for query: {query}")
                return []

            # Fetch full message details
            emails = []
            for message in messages:
                try:
                    msg = self._service.users().messages().get(
                        userId='me',
                        id=message['id'],
                        format='full'
                    ).execute()

                    email_obj = self._parser.parse(msg)
                    emails.append(email_obj)

                except Exception as e:
                    logger.warning(f"Failed to fetch message {message['id']}: {e}")
                    continue

            logger.info(f"Found {len(emails)} emails for query: {query}")
            return emails

        except Exception as e:
            logger.error(f"Error searching Gmail: {e}")
            return []
