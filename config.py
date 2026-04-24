"""Configuration management for AI Email Management Tool."""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

@dataclass
class GmailConfig:
    """Gmail API configuration."""
    credentials_file: str
    token_file: str

    @classmethod
    def from_env(cls) -> "GmailConfig":
        return cls(
            credentials_file=os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json"),
            token_file=os.getenv("GMAIL_TOKEN_FILE", "token.json")
        )

@dataclass
class IMAPConfig:
    """IMAP configuration for non-Gmail accounts."""
    server: str
    port: int
    email: str
    password: str

    @classmethod
    def from_env(cls) -> "IMAPConfig":
        return cls(
            server=os.getenv("IMAP_SERVER", "imap.gmail.com"),
            port=int(os.getenv("IMAP_PORT", "993")),
            email=os.getenv("IMAP_EMAIL", ""),
            password=os.getenv("IMAP_PASSWORD", "")
        )

@dataclass
class ClaudeConfig:
    """Claude API configuration."""
    api_key: str

    @classmethod
    def from_env(cls) -> "ClaudeConfig":
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY must be set in .env file")
        return cls(api_key=api_key)

@dataclass
class DatabaseConfig:
    """Database configuration."""
    path: Path

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        db_path = os.getenv("CACHE_DB_PATH", "email_cache.db")
        return cls(path=Path(db_path))

@dataclass
class AppConfig:
    """Application-wide configuration."""
    max_fetch_emails: int
    cache_max_age_days: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            max_fetch_emails=int(os.getenv("MAX_FETCH_EMAILS", "100")),
            cache_max_age_days=int(os.getenv("CACHE_MAX_AGE_DAYS", "30"))
        )

# Global configuration instances
gmail_config = GmailConfig.from_env()
imap_config = IMAPConfig.from_env()
claude_config = ClaudeConfig.from_env()
database_config = DatabaseConfig.from_env()
app_config = AppConfig.from_env()
