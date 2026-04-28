"""Gmail message parser."""

import logging
from datetime import datetime
from base64 import urlsafe_b64decode
from typing import Dict, Any

from providers.base import Email

logger = logging.getLogger(__name__)


class GmailMessageParser:
    """Parses Gmail API messages into Email objects.

    Single Responsibility: Message parsing only.
    No API calls, no authentication, no fetching logic.
    """

    def parse(self, msg: Dict[str, Any]) -> Email:
        """Parse Gmail API message into Email object.

        Args:
            msg: Gmail API message dictionary

        Returns:
            Email object
        """
        headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}

        # Extract basic fields
        subject = headers.get('Subject', '')
        sender = headers.get('From', '')
        recipient = headers.get('To', '')

        # Parse date
        date_str = headers.get('Date', '')
        received_date = self._parse_date(date_str)

        # Extract body (plain text only)
        body = self._extract_body(msg['payload'])

        # Check for attachments
        has_attachments = any(
            part.get('filename') for part in msg['payload'].get('parts', [])
        )

        # Check read status
        is_read = 'UNREAD' not in msg.get('labelIds', [])

        # Extract labels
        labels = msg.get('labelIds', [])

        return Email(
            id=msg['id'],
            subject=subject,
            sender=sender,
            recipient=recipient,
            body=body,
            html_body=None,  # Not storing HTML to save space
            received_date=received_date,
            has_attachments=has_attachments,
            is_read=is_read,
            labels=labels
        )

    def _parse_date(self, date_str: str) -> datetime:
        """Parse email date string.

        Args:
            date_str: Date string from email headers

        Returns:
            datetime object (now() if parsing fails)
        """
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to parse date '{date_str}': {e}")
            return datetime.now()

    def _extract_body(self, payload: Dict[str, Any]) -> str:
        """Extract plain text body from message payload.

        Recursively searches for text/plain parts.

        Args:
            payload: Gmail message payload

        Returns:
            Plain text body (empty string if not found)
        """
        body = ""

        def _extract_recursive(part: Dict[str, Any]) -> None:
            nonlocal body

            if 'parts' in part:
                for subpart in part['parts']:
                    _extract_recursive(subpart)
            else:
                mime_type = part.get('mimeType', '')
                if 'data' in part.get('body', {}):
                    data = part['body']['data']
                    decoded = urlsafe_b64decode(data).decode('utf-8', errors='ignore')

                    # Only take first plain text part
                    if mime_type == 'text/plain' and not body:
                        body = decoded

        _extract_recursive(payload)
        return body
