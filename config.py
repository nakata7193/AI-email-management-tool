"""Configuration management for AI Email Management Tool."""

import os
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Profile configuration file
PROFILES_FILE = Path.home() / ".claude" / "email-tool-profiles.json"

@dataclass
class GmailConfig:
    """Gmail API configuration."""
    credentials_file: str
    token_file: str

    @classmethod
    def from_env(cls, profile: Optional[str] = None) -> "GmailConfig":
        """Load Gmail configuration for a profile.

        If profile is provided, looks for files in data/{profile}/ directory.
        Otherwise uses root-level environment variables.
        """
        if profile:
            # User-specific directory structure: data/{profile}/credentials.json
            prefix = f"{profile.upper()}_"
            default_creds = f"data/{profile}/credentials.json"
            default_token = f"data/{profile}/token.json"
        else:
            prefix = ""
            default_creds = "credentials.json"
            default_token = "token.json"

        return cls(
            credentials_file=os.getenv(f"{prefix}GMAIL_CREDENTIALS_FILE", default_creds),
            token_file=os.getenv(f"{prefix}GMAIL_TOKEN_FILE", default_token)
        )

@dataclass
class IMAPConfig:
    """IMAP configuration for non-Gmail accounts."""
    server: str
    port: int
    email: str
    password: str

    @classmethod
    def from_env(cls, profile: Optional[str] = None) -> "IMAPConfig":
        prefix = f"{profile.upper()}_" if profile else ""
        return cls(
            server=os.getenv(f"{prefix}IMAP_SERVER", "imap.gmail.com"),
            port=int(os.getenv(f"{prefix}IMAP_PORT", "993")),
            email=os.getenv(f"{prefix}IMAP_EMAIL", ""),
            password=os.getenv(f"{prefix}IMAP_PASSWORD", "")
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
    def from_env(cls, profile: Optional[str] = None) -> "DatabaseConfig":
        """Load database configuration for a profile.

        If profile is provided, uses data/{profile}/email_cache.db.
        Otherwise uses CACHE_DB_PATH from env or email_cache.db.
        """
        if profile:
            # User-specific directory structure: data/{profile}/email_cache.db
            db_path = os.getenv("CACHE_DB_PATH", f"data/{profile}/email_cache.db")
        else:
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

class ProfileManager:
    """Manage multiple email account profiles."""

    def __init__(self):
        self.profiles_file = PROFILES_FILE
        self.profiles_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_profiles()

    def _load_profiles(self):
        """Load profiles from file."""
        if self.profiles_file.exists():
            with open(self.profiles_file, 'r') as f:
                self.data = json.load(f)
        else:
            self.data = {
                "active_profile": None,
                "profiles": {}
            }
            self._save_profiles()

    def _save_profiles(self):
        """Save profiles to file."""
        with open(self.profiles_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def create_profile(self, name: str, description: str, provider: str):
        """Create a new profile and its data directory."""
        self.data["profiles"][name] = {
            "description": description,
            "provider": provider,
            "created_at": str(Path(__file__).stat().st_mtime)
        }
        self._save_profiles()

        # Automatically create the profile's data directory
        profile_data_dir = Path("data") / name
        profile_data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created data directory: {profile_data_dir}")

    def list_profiles(self) -> dict:
        """List all profiles."""
        return self.data["profiles"]

    def get_active_profile(self) -> Optional[str]:
        """Get the active profile name."""
        return self.data.get("active_profile")

    def set_active_profile(self, name: str):
        """Set the active profile."""
        if name not in self.data["profiles"]:
            raise ValueError(f"Profile '{name}' does not exist")
        self.data["active_profile"] = name
        self._save_profiles()

    def delete_profile(self, name: str):
        """Delete a profile."""
        if name in self.data["profiles"]:
            del self.data["profiles"][name]
            if self.data["active_profile"] == name:
                self.data["active_profile"] = None
            self._save_profiles()

def get_config(profile: Optional[str] = None):
    """Get configuration for a specific profile or active profile."""
    if profile is None:
        profile_mgr = ProfileManager()
        profile = profile_mgr.get_active_profile()

    return {
        'gmail': GmailConfig.from_env(profile),
        'imap': IMAPConfig.from_env(profile),
        'claude': ClaudeConfig.from_env(),
        'database': DatabaseConfig.from_env(profile),
        'app': AppConfig.from_env()
    }

