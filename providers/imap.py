"""IMAP email provider implementation."""

import imaplib
import email
from email.header import decode_header
from typing import List, Optional
from datetime import datetime
import logging

from providers.base import EmailProvider, Email
from config import imap_config

logger = logging.getLogger(__name__)

class IMAPProvider(EmailProvider):
    """IMAP email provider implementation."""

    def __init__(self, config=None):
        self.connection: Optional[imaplib.IMAP4_SSL] = None
        self.config = config if config else imap_config

    def connect(self) -> None:
        """Establish connection to IMAP server."""
        try:
            self.connection = imaplib.IMAP4_SSL(self.config.server, self.config.port)
            self.connection.login(self.config.email, self.config.password)
            logger.info(f"Connected to IMAP server: {self.config.server}")
        except imaplib.IMAP4.error as e:
            logger.error(f"Failed to connect to IMAP server: {e}")
            raise ConnectionError(f"IMAP connection failed: {e}")

    def disconnect(self) -> None:
        """Close connection to IMAP server."""
        if self.connection:
            try:
                self.connection.logout()
                logger.info("Disconnected from IMAP server")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self.connection = None

    def _decode_header_value(self, header_value: str) -> str:
        """Decode email header value."""
        if not header_value:
            return ""

        decoded_parts = decode_header(header_value)
        result = []

        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                try:
                    result.append(part.decode(encoding or 'utf-8', errors='ignore'))
                except (LookupError, UnicodeDecodeError):
                    result.append(part.decode('utf-8', errors='ignore'))
            else:
                result.append(str(part))

        return ''.join(result)

    def _parse_email_message(self, msg_data: bytes) -> Email:
        """Parse raw email message into Email object."""
        msg = email.message_from_bytes(msg_data)

        # Extract basic fields
        subject = self._decode_header_value(msg.get("Subject", ""))
        sender = self._decode_header_value(msg.get("From", ""))
        recipient = self._decode_header_value(msg.get("To", ""))

        # Parse date
        date_str = msg.get("Date", "")
        try:
            received_date = email.utils.parsedate_to_datetime(date_str)
        except (TypeError, ValueError):
            received_date = datetime.now()

        # Extract body
        body = ""
        html_body = None
        has_attachments = False

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in content_disposition:
                    has_attachments = True
                elif content_type == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        pass
                elif content_type == "text/html":
                    try:
                        html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                body = str(msg.get_payload())

        # Generate unique ID from Message-ID header
        email_id = msg.get("Message-ID", str(hash(msg_data)))

        return Email(
            id=email_id,
            subject=subject,
            sender=sender,
            recipient=recipient,
            body=body,
            html_body=html_body,
            received_date=received_date,
            has_attachments=has_attachments,
            is_read=False,  # IMAP doesn't easily expose read status in fetch
            labels=[]
        )

    def fetch_emails(self, limit: int = 100, unread_only: bool = False) -> List[Email]:
        """Fetch emails from IMAP server."""
        if not self.connection:
            raise ConnectionError("Not connected to IMAP server. Call connect() first.")

        try:
            # Select inbox
            self.connection.select("INBOX")

            # Search for emails
            search_criteria = "UNSEEN" if unread_only else "ALL"
            status, messages = self.connection.search(None, search_criteria)

            if status != "OK":
                logger.error("Failed to search emails")
                return []

            # Get message IDs
            message_ids = messages[0].split()

            # Limit results
            message_ids = message_ids[-limit:] if len(message_ids) > limit else message_ids

            emails = []
            for msg_id in reversed(message_ids):  # Most recent first
                try:
                    status, msg_data = self.connection.fetch(msg_id, "(RFC822)")
                    if status == "OK":
                        email_obj = self._parse_email_message(msg_data[0][1])
                        emails.append(email_obj)
                except Exception as e:
                    logger.warning(f"Failed to parse email {msg_id}: {e}")
                    continue

            logger.info(f"Fetched {len(emails)} emails from IMAP")
            return emails

        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return []

    def mark_as_read(self, email_id: str) -> bool:
        """Mark an email as read."""
        if not self.connection:
            raise ConnectionError("Not connected to IMAP server")

        try:
            # Search for email by Message-ID
            self.connection.select("INBOX")
            status, messages = self.connection.search(None, f'HEADER Message-ID "{email_id}"')

            if status != "OK" or not messages[0]:
                logger.warning(f"Email {email_id} not found")
                return False

            msg_id = messages[0].split()[0]
            self.connection.store(msg_id, '+FLAGS', '\\Seen')
            logger.info(f"Marked email {email_id} as read")
            return True

        except Exception as e:
            logger.error(f"Error marking email as read: {e}")
            return False

    def get_email_by_id(self, email_id: str) -> Optional[Email]:
        """Retrieve a specific email by ID."""
        if not self.connection:
            raise ConnectionError("Not connected to IMAP server")

        try:
            self.connection.select("INBOX")
            status, messages = self.connection.search(None, f'HEADER Message-ID "{email_id}"')

            if status != "OK" or not messages[0]:
                return None

            msg_id = messages[0].split()[0]
            status, msg_data = self.connection.fetch(msg_id, "(RFC822)")

            if status == "OK":
                return self._parse_email_message(msg_data[0][1])

            return None

        except Exception as e:
            logger.error(f"Error retrieving email: {e}")
            return None
