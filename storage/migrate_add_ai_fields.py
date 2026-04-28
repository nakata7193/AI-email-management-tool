#!/usr/bin/env python3
"""Migration script to add AI analysis fields to existing database."""

import sqlite3
import sys

DB_PATH = "email_cache_atanas.db"


def migrate(db_path: str = DB_PATH):
    """Add AI analysis columns to existing emails table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check which columns already exist
    cursor.execute("PRAGMA table_info(emails)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    new_columns = [
        ("content_type", "TEXT"),
        ("importance", "TEXT"),
        ("contains_receipt", "BOOLEAN DEFAULT 0"),
        ("contains_tracking", "BOOLEAN DEFAULT 0"),
        ("requires_action", "BOOLEAN DEFAULT 0"),
        ("is_promotional", "BOOLEAN DEFAULT 0"),
        ("ai_analyzed", "BOOLEAN DEFAULT 0"),
        ("ai_analyzed_date", "TIMESTAMP"),
    ]

    added = 0
    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            print(f"Adding column: {col_name} ({col_type})")
            cursor.execute(f"ALTER TABLE emails ADD COLUMN {col_name} {col_type}")
            added += 1
        else:
            print(f"Column already exists: {col_name}")

    conn.commit()
    conn.close()

    print(f"\nMigration complete. Added {added} new columns.")
    return added


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    migrate(db)
