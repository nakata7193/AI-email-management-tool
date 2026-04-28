"""Gmail OAuth2 authentication handler."""

import os
import pickle
import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]


class GmailAuthenticator:
    """Handles Gmail OAuth2 authentication.

    Single Responsibility: Authentication and credential management only.
    Separated from API calls, parsing, and other concerns.
    """

    def __init__(self, credentials_file: str, token_file: str):
        """Initialize authenticator with file paths.

        Args:
            credentials_file: Path to OAuth2 credentials JSON
            token_file: Path to store/load token pickle
        """
        self._credentials_file = credentials_file
        self._token_file = token_file

    def get_credentials(self) -> Credentials:
        """Get or refresh Gmail API credentials.

        Returns:
            Valid OAuth2 credentials

        Raises:
            FileNotFoundError: If credentials file doesn't exist
        """
        creds = None

        # Load token from file if exists
        if os.path.exists(self._token_file):
            with open(self._token_file, 'rb') as token:
                creds = pickle.load(token)
                logger.debug(f"Loaded credentials from {self._token_file}")

        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired credentials")
                creds.refresh(Request())
            else:
                if not os.path.exists(self._credentials_file):
                    raise FileNotFoundError(
                        f"Gmail credentials file not found: {self._credentials_file}\n"
                        "Please download credentials.json from Google Cloud Console"
                    )

                logger.info("Starting OAuth2 flow")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self._credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save credentials for next run
            with open(self._token_file, 'wb') as token:
                pickle.dump(creds, token)
                logger.debug(f"Saved credentials to {self._token_file}")

        return creds
