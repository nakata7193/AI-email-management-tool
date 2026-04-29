"""IMAP email provider implementation."""

import imaplib
import email
from email.header import decode_header
from typing import List, Optional
from datetime import datetime
import logging

from providers.base import EmailProvider, Email

logger = logging.getLogger(__name__)

class IMAPProvider(EmailProvider):
    """IMAP email provider implementation."""

    def __init__(self, config):
        """Initialize IMAP provider with explicit configuration.

        Args:
            config: IMAPConfig instance (required, no defaults)
        """
        if not config:
            raise ValueError("IMAPConfig is required")
        self.connection: Optional[imaplib.IMAP4_SSL] = None
        self.config = config

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

    def _find_message_id(self, email_id: str) -> Optional[bytes]:
        """Select INBOX and find IMAP message number by Message-ID header.

        Args:
            email_id: Email Message-ID header value

        Returns:
            IMAP message number bytes, or None if not found
        """
        self.connection.select("INBOX")
        status, messages = self.connection.search(None, f'HEADER Message-ID "{email_id}"')

        if status != "OK" or not messages[0]:
            return None

        return messages[0].split()[0]

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
            msg_id = self._find_message_id(email_id)

            if not msg_id:
                logger.warning(f"Email {email_id} not found")
                return False

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
            msg_id = self._find_message_id(email_id)

            if not msg_id:
                return None

            status, msg_data = self.connection.fetch(msg_id, "(RFC822)")
            if status == "OK":
                return self._parse_email_message(msg_data[0][1])

            return None

        except Exception as e:
            logger.error(f"Error retrieving email: {e}")
            return None

    def mark_as_unread(self, email_id: str) -> bool:
        """Mark an email as unread."""
        if not self.connection:
            raise ConnectionError("Not connected to IMAP server")

        try:
            msg_id = self._find_message_id(email_id)

            if not msg_id:
                logger.warning(f"Email {email_id} not found")
                return False

            self.connection.store(msg_id, '-FLAGS', '\\Seen')
            logger.info(f"Marked email {email_id} as unread")
            return True

        except Exception as e:
            logger.error(f"Error marking email as unread: {e}")
            return False

    def delete_email(self, email_id: str, expunge: bool = False) -> bool:
        """
        Delete an email by marking it with \\Deleted flag.

        Args:
            email_id: Email Message-ID to delete
            expunge: If True, permanently remove the email immediately.
                    If False, just mark for deletion (can be undeleted later).

        Returns:
            True if successful, False otherwise

        Note:
            - With expunge=False: Email marked for deletion but still in mailbox
            - With expunge=True: Email permanently removed immediately
            - Some servers auto-expunge on logout
        """
        if not self.connection:
            raise ConnectionError("Not connected to IMAP server")

        try:
            msg_id = self._find_message_id(email_id)

            if not msg_id:
                logger.warning(f"Email {email_id} not found")
                return False

            self.connection.store(msg_id, '+FLAGS', '\\Deleted')
            logger.info(f"Marked email {email_id} for deletion")

            if expunge:
                self.connection.expunge()
                logger.info(f"Permanently deleted email {email_id}")

            return True

        except Exception as e:
            logger.error(f"Error deleting email: {e}")
            return False

    def move_email(self, email_id: str, destination_folder: str) -> bool:
        """
        Move an email to a different folder.

        Args:
            email_id: Email Message-ID to move
            destination_folder: Destination folder name (e.g., 'Archive', 'Spam')

        Returns:
            True if successful, False otherwise

        Note:
            IMAP "move" is implemented as COPY + DELETE:
            1. Copy email to destination folder
            2. Mark original as deleted
            3. Expunge to remove original
        """
        if not self.connection:
            raise ConnectionError("Not connected to IMAP server")

        try:
            msg_id = self._find_message_id(email_id)

            if not msg_id:
                logger.warning(f"Email {email_id} not found")
                return False

            result = self.connection.copy(msg_id, destination_folder)
            if result[0] != 'OK':
                logger.error(f"Failed to copy email to {destination_folder}")
                return False

            self.connection.store(msg_id, '+FLAGS', '\\Deleted')
            self.connection.expunge()

            logger.info(f"Moved email {email_id} to {destination_folder}")
            return True

        except Exception as e:
            logger.error(f"Error moving email: {e}")
            return False

    def flag_email(self, email_id: str, flagged: bool = True) -> bool:
        """
        Flag/star an email (mark as important).

        Args:
            email_id: Email Message-ID to flag
            flagged: True to flag, False to unflag

        Returns:
            True if successful, False otherwise
        """
        if not self.connection:
            raise ConnectionError("Not connected to IMAP server")

        try:
            msg_id = self._find_message_id(email_id)

            if not msg_id:
                logger.warning(f"Email {email_id} not found")
                return False

            if flagged:
                self.connection.store(msg_id, '+FLAGS', '\\Flagged')
                logger.info(f"Flagged email {email_id}")
            else:
                self.connection.store(msg_id, '-FLAGS', '\\Flagged')
                logger.info(f"Unflagged email {email_id}")

            return True

        except Exception as e:
            logger.error(f"Error flagging email: {e}")
            return False

    def list_folders(self) -> List[str]:
        """
        List all available folders/mailboxes.

        Returns:
            List of folder names (e.g., ['INBOX', 'Sent', 'Drafts', 'Archive'])
        """
        if not self.connection:
            raise ConnectionError("Not connected to IMAP server")

        try:
            status, folders = self.connection.list()

            if status != "OK":
                return []

            folder_names = []
            for folder in folders:
                # Parse folder name from IMAP response
                # Format: (\\HasNoChildren) "." "INBOX.Sent"
                parts = folder.decode().split('"')
                if len(parts) >= 3:
                    folder_name = parts[-2]
                    folder_names.append(folder_name)

            logger.info(f"Found {len(folder_names)} folders")
            return folder_names

        except Exception as e:
            logger.error(f"Error listing folders: {e}")
            return []

    def expunge_deleted(self) -> bool:
        """
        Permanently remove all emails marked for deletion.

        Returns:
            True if successful, False otherwise

        Note:
            This affects ALL emails marked with \\Deleted flag in current folder.
            Use carefully!
        """
        if not self.connection:
            raise ConnectionError("Not connected to IMAP server")

        try:
            self.connection.select("INBOX")
            self.connection.expunge()
            logger.info("Expunged deleted emails from INBOX")
            return True

        except Exception as e:
            logger.error(f"Error expunging deleted emails: {e}")
            return False
