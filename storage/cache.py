"""SQLite caching layer for emails."""

import sqlite3
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import logging

from providers.base import Email
from config import database_config, app_config

logger = logging.getLogger(__name__)

class EmailCache:
    """SQLite-based email caching system."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or database_config.path
        self.connection: Optional[sqlite3.Connection] = None
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize database and create tables if they don't exist."""
        try:
            self.connection = sqlite3.connect(
                str(self.db_path),
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            self.connection.row_factory = sqlite3.Row

            # Read and execute schema
            schema_path = Path(__file__).parent / 'schema.sql'
            with open(schema_path, 'r') as f:
                schema = f.read()

            self.connection.executescript(schema)
            self.connection.commit()

            logger.info(f"Initialized database at {self.db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def store_email(self, email: Email, provider: str,
                   category: Optional[str] = None,
                   summary: Optional[str] = None) -> bool:
        """
        Store or update an email in the cache.

        Args:
            email: Email object to store
            provider: Email provider name (gmail, imap)
            category: AI-generated category
            summary: AI-generated summary

        Returns:
            True if successful, False otherwise
        """
        try:
            cursor = self.connection.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO emails (
                    id, subject, sender, recipient, body, html_body,
                    received_date, has_attachments, is_read, provider,
                    labels, category, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                email.id,
                email.subject,
                email.sender,
                email.recipient,
                email.body,
                email.html_body,
                email.received_date,
                email.has_attachments,
                email.is_read,
                provider,
                json.dumps(email.labels),
                category,
                summary
            ))

            self.connection.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to store email {email.id}: {e}")
            return False

    def get_email(self, email_id: str, provider: Optional[str] = None) -> Optional[Email]:
        """
        Retrieve an email from cache by ID.

        Args:
            email_id: Email ID
            provider: Optional provider filter

        Returns:
            Email object if found, None otherwise
        """
        try:
            cursor = self.connection.cursor()

            if provider:
                cursor.execute(
                    "SELECT * FROM emails WHERE id = ? AND provider = ?",
                    (email_id, provider)
                )
            else:
                cursor.execute("SELECT * FROM emails WHERE id = ?", (email_id,))

            row = cursor.fetchone()

            if row:
                return self._row_to_email(row)

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve email {email_id}: {e}")
            return None

    def get_emails(self,
                  limit: int = 100,
                  unread_only: bool = False,
                  category: Optional[str] = None,
                  provider: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve multiple emails from cache with filters.

        Args:
            limit: Maximum number of emails to return
            unread_only: Only return unread emails
            category: Filter by category
            provider: Filter by provider

        Returns:
            List of email dictionaries with metadata
        """
        try:
            cursor = self.connection.cursor()

            query = "SELECT * FROM emails WHERE 1=1"
            params = []

            if unread_only:
                query += " AND is_read = 0"

            if category:
                query += " AND category = ?"
                params.append(category)

            if provider:
                query += " AND provider = ?"
                params.append(provider)

            query += " ORDER BY received_date DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to retrieve emails: {e}")
            return []

    def search_emails(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Full-text search emails.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching emails
        """
        try:
            cursor = self.connection.cursor()

            # Log search
            cursor.execute(
                "INSERT INTO search_history (query) VALUES (?)",
                (query,)
            )

            # Perform FTS search
            cursor.execute("""
                SELECT emails.*
                FROM emails_fts
                JOIN emails ON emails.rowid = emails_fts.rowid
                WHERE emails_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))

            rows = cursor.fetchall()

            # Update search results count
            cursor.execute(
                "UPDATE search_history SET results_count = ? WHERE rowid = last_insert_rowid()",
                (len(rows),)
            )

            self.connection.commit()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def update_category(self, email_id: str, category: str, reasoning: Optional[str] = None) -> bool:
        """Update email category."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "UPDATE emails SET category = ?, category_reasoning = ? WHERE id = ?",
                (category, reasoning, email_id)
            )
            self.connection.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to update category: {e}")
            return False

    def update_summary(self, email_id: str, summary: str, action_items: Optional[str] = None) -> bool:
        """Update email summary."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "UPDATE emails SET summary = ?, action_items = ? WHERE id = ?",
                (summary, action_items, email_id)
            )
            self.connection.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to update summary: {e}")
            return False

    def clean_old_emails(self, days: Optional[int] = None) -> int:
        """
        Remove emails older than specified days.

        Args:
            days: Number of days to keep (default from config)

        Returns:
            Number of emails deleted
        """
        days = days or app_config.cache_max_age_days

        try:
            cursor = self.connection.cursor()
            cutoff_date = datetime.now() - timedelta(days=days)

            cursor.execute(
                "DELETE FROM emails WHERE fetched_date < ?",
                (cutoff_date,)
            )

            self.connection.commit()
            deleted_count = cursor.rowcount

            logger.info(f"Cleaned {deleted_count} old emails")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to clean old emails: {e}")
            return 0

    def get_statistics(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            cursor = self.connection.cursor()

            stats = {}

            # Total emails
            cursor.execute("SELECT COUNT(*) FROM emails")
            stats['total_emails'] = cursor.fetchone()[0]

            # Unread count
            cursor.execute("SELECT COUNT(*) FROM emails WHERE is_read = 0")
            stats['unread_emails'] = cursor.fetchone()[0]

            # By category
            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM emails
                WHERE category IS NOT NULL
                GROUP BY category
            """)
            stats['by_category'] = dict(cursor.fetchall())

            # By provider
            cursor.execute("""
                SELECT provider, COUNT(*) as count
                FROM emails
                GROUP BY provider
            """)
            stats['by_provider'] = dict(cursor.fetchall())

            return stats

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    def _row_to_email(self, row: sqlite3.Row) -> Email:
        """Convert database row to Email object."""
        return Email(
            id=row['id'],
            subject=row['subject'],
            sender=row['sender'],
            recipient=row['recipient'],
            body=row['body'],
            html_body=row['html_body'],
            received_date=row['received_date'],
            has_attachments=bool(row['has_attachments']),
            is_read=bool(row['is_read']),
            labels=json.loads(row['labels']) if row['labels'] else []
        )

    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logger.info("Closed database connection")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
