"""Gmail email modifier - handles email actions like mark read, delete, etc."""

import logging
from typing import Dict, List, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from providers.base import Email
from providers.gmail_components.parser import GmailMessageParser

logger = logging.getLogger(__name__)


class GmailModifier:
    """Modifies Gmail messages (mark read/unread, delete, move, etc).

    Single Responsibility: Email modification operations only.
    No fetching, no authentication, no parsing.
    """

    def __init__(self, parser: Optional[GmailMessageParser] = None):
        """Initialize modifier.

        Args:
            parser: Message parser (needed for get_email_by_id)
        """
        self._parser = parser or GmailMessageParser()
        self._service = None

    def set_credentials(self, creds: Credentials) -> None:
        """Set Gmail API credentials.

        Args:
            creds: OAuth2 credentials
        """
        self._service = build('gmail', 'v1', credentials=creds)
        logger.debug("Gmail service initialized for modifier")

    def mark_as_read(self, email_id: str) -> bool:
        """Mark a Gmail message as read.

        Args:
            email_id: Gmail message ID

        Returns:
            True if successful, False otherwise
        """
        if not self._service:
            raise RuntimeError("Service not initialized. Call set_credentials() first.")

        try:
            self._service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()

            logger.info(f"Marked email {email_id} as read")
            return True

        except Exception as e:
            logger.error(f"Error marking email as read: {e}")
            return False

    def mark_as_unread(self, email_id: str) -> bool:
        """Mark a Gmail message as unread.

        Args:
            email_id: Gmail message ID

        Returns:
            True if successful, False otherwise
        """
        if not self._service:
            raise RuntimeError("Service not initialized. Call set_credentials() first.")

        try:
            self._service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'addLabelIds': ['UNREAD']}
            ).execute()

            logger.info(f"Marked email {email_id} as unread")
            return True

        except Exception as e:
            logger.error(f"Error marking email as unread: {e}")
            return False

    def delete_email(self, email_id: str, permanent: bool = False) -> bool:
        """Delete a Gmail message.

        Args:
            email_id: Gmail message ID
            permanent: If True, permanently delete (bypass trash).
                      If False, move to trash (can be recovered).

        Returns:
            True if successful, False otherwise
        """
        if not self._service:
            raise RuntimeError("Service not initialized. Call set_credentials() first.")

        try:
            if permanent:
                self._service.users().messages().delete(
                    userId='me',
                    id=email_id
                ).execute()
                logger.info(f"Permanently deleted email {email_id}")
            else:
                self._service.users().messages().trash(
                    userId='me',
                    id=email_id
                ).execute()
                logger.info(f"Moved email {email_id} to trash")

            return True

        except Exception as e:
            logger.error(f"Error deleting email: {e}")
            return False

    def untrash_email(self, email_id: str) -> bool:
        """Restore an email from trash.

        Args:
            email_id: Gmail message ID

        Returns:
            True if successful, False otherwise
        """
        if not self._service:
            raise RuntimeError("Service not initialized. Call set_credentials() first.")

        try:
            self._service.users().messages().untrash(
                userId='me',
                id=email_id
            ).execute()

            logger.info(f"Restored email {email_id} from trash")
            return True

        except Exception as e:
            logger.error(f"Error restoring email from trash: {e}")
            return False

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
            True if successful, False otherwise
        """
        if not self._service:
            raise RuntimeError("Service not initialized. Call set_credentials() first.")

        try:
            body = {}
            if add_labels:
                body['addLabelIds'] = add_labels
            if remove_labels:
                body['removeLabelIds'] = remove_labels

            self._service.users().messages().modify(
                userId='me',
                id=email_id,
                body=body
            ).execute()

            logger.info(f"Modified labels for email {email_id}: +{add_labels} -{remove_labels}")
            return True

        except Exception as e:
            logger.error(f"Error moving email: {e}")
            return False

    def archive_email(self, email_id: str) -> bool:
        """Archive an email (remove from INBOX).

        Args:
            email_id: Gmail message ID

        Returns:
            True if successful, False otherwise
        """
        return self.move_email(email_id, remove_labels=['INBOX'])

    def star_email(self, email_id: str, starred: bool = True) -> bool:
        """Star/unstar an email.

        Args:
            email_id: Gmail message ID
            starred: True to star, False to unstar

        Returns:
            True if successful, False otherwise
        """
        if starred:
            return self.move_email(email_id, add_labels=['STARRED'])
        else:
            return self.move_email(email_id, remove_labels=['STARRED'])

    def mark_as_spam(self, email_id: str) -> bool:
        """Mark an email as spam.

        Args:
            email_id: Gmail message ID

        Returns:
            True if successful, False otherwise
        """
        return self.move_email(email_id, add_labels=['SPAM'], remove_labels=['INBOX'])

    def list_labels(self) -> List[dict]:
        """List all Gmail labels.

        Returns:
            List of label dictionaries with 'id', 'name', 'type' keys
        """
        if not self._service:
            raise RuntimeError("Service not initialized. Call set_credentials() first.")

        try:
            results = self._service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])

            logger.info(f"Found {len(labels)} labels")
            return labels

        except Exception as e:
            logger.error(f"Error listing labels: {e}")
            return []

    def create_label(self, name: str) -> Optional[str]:
        """Create a Gmail label and return its ID.

        Args:
            name: Label name to create

        Returns:
            Label ID if created successfully, None on error
        """
        if not self._service:
            raise RuntimeError("Service not initialized. Call set_credentials() first.")

        try:
            label = self._service.users().labels().create(
                userId='me',
                body={'name': name, 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'}
            ).execute()

            logger.info(f"Created label '{name}' with ID {label['id']}")
            return label['id']

        except Exception as e:
            logger.error(f"Error creating label '{name}': {e}")
            return None

    def ensure_labels(self, names: List[str]) -> Dict[str, str]:
        """Ensure all given labels exist in Gmail, creating missing ones.

        Args:
            names: List of label names to ensure exist

        Returns:
            Dict mapping label name -> label ID for all requested labels
        """
        existing = {label['name']: label['id'] for label in self.list_labels()}
        label_map: Dict[str, str] = {}

        for name in names:
            if name in existing:
                label_map[name] = existing[name]
            else:
                label_id = self.create_label(name)
                if label_id:
                    label_map[name] = label_id
                else:
                    logger.warning(f"Could not create label '{name}', skipping")

        return label_map

    def get_email_by_id(self, email_id: str) -> Optional[Email]:
        """Retrieve a specific Gmail message by ID.

        Args:
            email_id: Gmail message ID

        Returns:
            Email object or None if not found
        """
        if not self._service:
            raise RuntimeError("Service not initialized. Call set_credentials() first.")

        try:
            msg = self._service.users().messages().get(
                userId='me',
                id=email_id,
                format='full'
            ).execute()

            return self._parser.parse(msg)

        except Exception as e:
            logger.error(f"Error retrieving email: {e}")
            return None
