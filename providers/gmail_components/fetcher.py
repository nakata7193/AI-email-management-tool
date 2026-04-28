"""Gmail email fetcher with parallel processing and retry logic."""

import logging
import time
from typing import List, Optional, Dict, Any
from socket import gaierror
from urllib.error import URLError
from http.client import RemoteDisconnected
from concurrent.futures import ThreadPoolExecutor, as_completed

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from providers.base import Email
from providers.gmail_components.parser import GmailMessageParser

logger = logging.getLogger(__name__)


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
        unread_only: bool = False
    ) -> List[str]:
        """Get message IDs from inbox (lightweight, no content).

        Args:
            limit: Maximum number of IDs to return (None = all)
            unread_only: Only get unread message IDs

        Returns:
            List of message IDs
        """
        if not self._service:
            raise RuntimeError("Service not initialized. Call set_credentials() first.")

        query = 'is:unread' if unread_only else ''
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

        Thread-safe - creates own service instance.

        Args:
            message_id: Gmail message ID

        Returns:
            Email object or None if fetch failed
        """
        retry_count = 0
        max_retries = 5

        # Create thread-safe service instance
        service = self._get_thread_safe_service()

        while retry_count < max_retries:
            try:
                msg = service.users().messages().get(
                    userId='me',
                    id=message_id,
                    format='full'
                ).execute()

                return self._parser.parse(msg)

            except (ConnectionError, gaierror, URLError, RemoteDisconnected, OSError) as e:
                retry_count += 1
                wait_time = min(30 * (2 ** retry_count), 300)

                if retry_count < max_retries:
                    logger.warning(
                        f"Network error fetching message {message_id} "
                        f"(attempt {retry_count}/{max_retries}): {e}"
                    )
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Failed to fetch message {message_id} "
                        f"after {max_retries} attempts: {e}"
                    )
                    return None

            except HttpError as e:
                if e.resp.status in [429, 503]:
                    retry_count += 1
                    wait_time = min(60 * retry_count, 300)

                    if retry_count < max_retries:
                        logger.warning(
                            f"Gmail API rate limit hit "
                            f"(attempt {retry_count}/{max_retries})"
                        )
                        logger.info(f"Waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"Failed to fetch message {message_id} "
                            f"after {max_retries} rate limit retries"
                        )
                        return None
                else:
                    logger.warning(f"HTTP error fetching message {message_id}: {e}")
                    return None

            except Exception as e:
                logger.warning(f"Failed to fetch message {message_id}: {e}")
                return None

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
        max_workers: int = 10
    ) -> List[Email]:
        """Fetch emails from Gmail with parallel processing.

        Args:
            limit: Maximum number of emails to fetch
            unread_only: Only fetch unread emails
            max_workers: Number of parallel workers (default: 10)

        Returns:
            List of Email objects
        """
        if not self._service:
            raise RuntimeError("Service not initialized. Call set_credentials() first.")

        try:
            # Build query
            query = 'is:unread' if unread_only else ''

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

    def analyze_top_senders(self, limit: Optional[int] = None) -> Dict[str, int]:
        """Analyze Gmail to find top senders by email count.

        Only fetches metadata (sender info), not full emails.

        Args:
            limit: Number of recent emails to analyze (None = ALL emails)

        Returns:
            Dictionary mapping sender to email count
        """
        if not self._service:
            raise RuntimeError("Service not initialized. Call set_credentials() first.")

        try:
            if limit:
                logger.info(f"Analyzing top senders from last {limit} emails...")
            else:
                logger.info("Analyzing ALL emails (may take 30-45 min for 40K emails)...")

            # Fetch all message IDs
            all_messages = []
            page_token = None

            while True:
                batch_size = min(500, limit - len(all_messages)) if limit else 500

                results = self._service.users().messages().list(
                    userId='me',
                    maxResults=batch_size,
                    pageToken=page_token
                ).execute()

                messages = results.get('messages', [])
                all_messages.extend(messages)

                page_token = results.get('nextPageToken')

                if not page_token or (limit and len(all_messages) >= limit):
                    break

                if len(all_messages) % 1000 == 0:
                    logger.info(f"Fetched {len(all_messages)} message IDs...")

            if not all_messages:
                logger.info("No messages found")
                return {}

            logger.info(f"Found {len(all_messages)} total emails. Analyzing senders...")

            # Count senders
            sender_counts = {}

            for i, message in enumerate(all_messages):
                try:
                    # Fetch only headers (metadata), not full message body
                    msg = self._service.users().messages().get(
                        userId='me',
                        id=message['id'],
                        format='metadata',
                        metadataHeaders=['From']
                    ).execute()

                    # Extract sender from headers
                    headers = msg['payload'].get('headers', [])
                    sender = None
                    for header in headers:
                        if header['name'] == 'From':
                            sender = header['value']
                            break

                    if sender:
                        sender_counts[sender] = sender_counts.get(sender, 0) + 1

                    if (i + 1) % 1000 == 0:
                        logger.info(f"Analyzed {i + 1}/{len(all_messages)} emails...")

                except Exception as e:
                    logger.warning(
                        f"Failed to fetch metadata for message {message['id']}: {e}"
                    )
                    continue

            logger.info(
                f"Analysis complete. Found {len(sender_counts)} unique senders "
                f"from {len(all_messages)} emails"
            )
            return sender_counts

        except Exception as e:
            logger.error(f"Error analyzing senders: {e}")
            return {}
