"""Abstract base class for email providers."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Email:
    """Email data structure."""
    id: str
    subject: str
    sender: str
    recipient: str
    body: str
    html_body: Optional[str]
    received_date: datetime
    has_attachments: bool
    is_read: bool
    labels: List[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Email':
        """Convert dictionary to Email object.

        Centralized conversion logic to avoid duplication across the codebase.
        Handles date string parsing with graceful fallback.

        Args:
            data: Email dictionary from database or API

        Returns:
            Email object
        """
        received_date = data['received_date']
        if isinstance(received_date, str):
            try:
                received_date = datetime.fromisoformat(received_date)
            except (ValueError, TypeError):
                received_date = datetime.now()

        return cls(
            id=data['id'],
            subject=data['subject'],
            sender=data['sender'],
            recipient=data['recipient'],
            body=data['body'],
            html_body=data.get('html_body'),
            received_date=received_date,
            has_attachments=data['has_attachments'],
            is_read=data['is_read'],
            labels=data.get('labels', [])
        )

class EmailProvider(ABC):
    """Abstract interface for email providers."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to email provider."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to email provider."""
        pass

    @abstractmethod
    def fetch_emails(self, limit: int = 100, unread_only: bool = False) -> List[Email]:
        """
        Fetch emails from the provider.

        Args:
            limit: Maximum number of emails to fetch
            unread_only: If True, only fetch unread emails

        Returns:
            List of Email objects
        """
        pass

    @abstractmethod
    def mark_as_read(self, email_id: str) -> bool:
        """
        Mark an email as read.

        Args:
            email_id: Unique identifier for the email

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_email_by_id(self, email_id: str) -> Optional[Email]:
        """
        Retrieve a specific email by ID.

        Args:
            email_id: Unique identifier for the email

        Returns:
            Email object if found, None otherwise
        """
        pass
