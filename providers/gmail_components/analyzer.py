"""Gmail sender analysis component."""

import logging
from typing import Dict, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


class GmailAnalyzer:
    """Analyzes Gmail metadata (senders, patterns).

    Single Responsibility: analysis operations only, no email fetching.
    Only fetches message metadata headers, not full email bodies.
    """

    def __init__(self):
        self._service = None

    def set_credentials(self, creds: Credentials) -> None:
        """Set Gmail API credentials.

        Args:
            creds: OAuth2 credentials
        """
        self._service = build('gmail', 'v1', credentials=creds)

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

            # Fetch all message IDs (metadata only)
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

            sender_counts: Dict[str, int] = {}

            for i, message in enumerate(all_messages):
                try:
                    msg = self._service.users().messages().get(
                        userId='me',
                        id=message['id'],
                        format='metadata',
                        metadataHeaders=['From']
                    ).execute()

                    headers = msg['payload'].get('headers', [])
                    for header in headers:
                        if header['name'] == 'From':
                            sender = header['value']
                            sender_counts[sender] = sender_counts.get(sender, 0) + 1
                            break

                    if (i + 1) % 1000 == 0:
                        logger.info(f"Analyzed {i + 1}/{len(all_messages)} emails...")

                except Exception as e:
                    logger.warning(f"Failed to fetch metadata for message {message['id']}: {e}")
                    continue

            logger.info(
                f"Analysis complete. Found {len(sender_counts)} unique senders "
                f"from {len(all_messages)} emails"
            )
            return sender_counts

        except Exception as e:
            logger.error(f"Error analyzing senders: {e}")
            return {}
