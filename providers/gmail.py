"""Gmail API provider implementation."""

import os
import pickle
from typing import List, Optional
from datetime import datetime
from base64 import urlsafe_b64decode
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from providers.base import EmailProvider, Email
from config import gmail_config

logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/gmail.modify']

class GmailProvider(EmailProvider):
    """Gmail API provider implementation."""

    def __init__(self, config=None):
        self.service = None
        self.config = config if config else gmail_config

    def _get_credentials(self) -> Credentials:
        """Get or refresh Gmail API credentials."""
        creds = None

        # Load token from file if exists
        if os.path.exists(self.config.token_file):
            with open(self.config.token_file, 'rb') as token:
                creds = pickle.load(token)

        # If no valid credentials, let user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.config.credentials_file):
                    raise FileNotFoundError(
                        f"Gmail credentials file not found: {self.config.credentials_file}\n"
                        "Please download credentials.json from Google Cloud Console"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.config.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)

            # Save credentials for next run
            with open(self.config.token_file, 'wb') as token:
                pickle.dump(creds, token)

        return creds

    def connect(self) -> None:
        """Establish connection to Gmail API."""
        try:
            creds = self._get_credentials()
            self.service = build('gmail', 'v1', credentials=creds)
            logger.info("Connected to Gmail API")
        except Exception as e:
            logger.error(f"Failed to connect to Gmail API: {e}")
            raise ConnectionError(f"Gmail API connection failed: {e}")

    def disconnect(self) -> None:
        """Close connection to Gmail API."""
        self.service = None
        logger.info("Disconnected from Gmail API")

    def _parse_gmail_message(self, msg: dict) -> Email:
        """Parse Gmail API message into Email object."""
        headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}

        # Extract basic fields
        subject = headers.get('Subject', '')
        sender = headers.get('From', '')
        recipient = headers.get('To', '')

        # Parse date
        date_str = headers.get('Date', '')
        try:
            from email.utils import parsedate_to_datetime
            received_date = parsedate_to_datetime(date_str)
        except (TypeError, ValueError):
            received_date = datetime.now()

        # Extract body
        body = ""
        html_body = None

        def extract_body(payload):
            nonlocal body, html_body

            if 'parts' in payload:
                for part in payload['parts']:
                    extract_body(part)
            else:
                mime_type = payload.get('mimeType', '')
                if 'data' in payload.get('body', {}):
                    data = payload['body']['data']
                    decoded = urlsafe_b64decode(data).decode('utf-8', errors='ignore')

                    if mime_type == 'text/plain' and not body:
                        body = decoded
                    elif mime_type == 'text/html' and not html_body:
                        html_body = decoded

        extract_body(msg['payload'])

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
            html_body=html_body,
            received_date=received_date,
            has_attachments=has_attachments,
            is_read=is_read,
            labels=labels
        )

    def fetch_emails(self, limit: int = 100, unread_only: bool = False) -> List[Email]:
        """Fetch emails from Gmail."""
        if not self.service:
            raise ConnectionError("Not connected to Gmail API. Call connect() first.")

        try:
            # Build query
            query = 'is:unread' if unread_only else ''

            # List messages
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=limit
            ).execute()

            messages = results.get('messages', [])

            if not messages:
                logger.info("No messages found")
                return []

            # Fetch full message details
            emails = []
            for message in messages:
                try:
                    msg = self.service.users().messages().get(
                        userId='me',
                        id=message['id'],
                        format='full'
                    ).execute()

                    email_obj = self._parse_gmail_message(msg)
                    emails.append(email_obj)

                except Exception as e:
                    logger.warning(f"Failed to fetch message {message['id']}: {e}")
                    continue

            logger.info(f"Fetched {len(emails)} emails from Gmail")
            return emails

        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return []

    def mark_as_read(self, email_id: str) -> bool:
        """Mark a Gmail message as read."""
        if not self.service:
            raise ConnectionError("Not connected to Gmail API")

        try:
            self.service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()

            logger.info(f"Marked email {email_id} as read")
            return True

        except Exception as e:
            logger.error(f"Error marking email as read: {e}")
            return False

    def get_email_by_id(self, email_id: str) -> Optional[Email]:
        """Retrieve a specific Gmail message by ID."""
        if not self.service:
            raise ConnectionError("Not connected to Gmail API")

        try:
            msg = self.service.users().messages().get(
                userId='me',
                id=email_id,
                format='full'
            ).execute()

            return self._parse_gmail_message(msg)

        except Exception as e:
            logger.error(f"Error retrieving email: {e}")
            return None
