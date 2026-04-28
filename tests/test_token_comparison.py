#!/usr/bin/env python3
"""Compare token usage between compact and JSON response formats.

This test uses the ACTUAL functions and captures real prompts/responses.
Results are saved to tests/results/
"""

import sqlite3
import os
import json
from datetime import datetime
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# Paths relative to project root (run from project root)
DB_PATH = "email_cache_atanas.db"
RESULTS_DIR = "tests/results"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def get_10_random_emails():
    """Get 10 random analyzed emails."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, subject, sender, body
        FROM emails
        WHERE ai_analyzed = 1
        ORDER BY RANDOM()
        LIMIT 10
    """)
    emails = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return emails


def load_categories():
    """Load categories from config."""
    config_file = "email_config.json"
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
            return config.get('categories', {})
    return {}


def test_compact_format(client, emails, categories):
    """Test the COMPACT format - mirrors analyze_emails_batch exactly."""

    # Build prompt - EXACTLY as in ai_analyze_emails.py
    email_summaries = []
    for i, email in enumerate(emails, 1):
        body = email.get('body', '')[:1500] if email.get('body') else ''
        email_summaries.append(f"""
{i}. Subject: {email.get('subject', 'No subject')}
   From: {email.get('sender', 'Unknown')}
   Body: {body[:400]}""")

    all_emails_text = "\n".join(email_summaries)

    prompt = f"""Categorize these {len(emails)} emails.

{all_emails_text}

Categories (use ONLY these, use "other" if unsure): {', '.join(categories.keys()) if categories else 'receipt, shipping, account_security, promotional, newsletter, personal, other'}

Response: one line per email
<number>. <category>

Example:
1. shipping
2. promotional
3. other"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )

    return {
        'format': 'COMPACT',
        'prompt': prompt,
        'response': response.content[0].text,
        'input_tokens': response.usage.input_tokens,
        'output_tokens': response.usage.output_tokens,
        'total_tokens': response.usage.input_tokens + response.usage.output_tokens
    }


def test_json_format(client, emails, categories):
    """Test the OLD JSON format for comparison."""

    # Build prompt - the OLD way
    email_summaries = []
    for i, email in enumerate(emails, 1):
        body = email.get('body', '')[:1500] if email.get('body') else ''
        email_summaries.append(f"""
EMAIL {i}:
- ID: {email.get('id', 'unknown')}
- Subject: {email.get('subject', 'No subject')}
- From: {email.get('sender', 'Unknown')}
- Body Preview: {body[:500]}...
""")

    all_emails_text = "\n".join(email_summaries)

    # Build categories list
    if categories:
        lines = []
        for cat_name in categories.keys():
            readable = cat_name.replace('_', ' ')
            lines.append(f"- {cat_name}: {readable}")
        categories_list = "\n".join(lines)
    else:
        categories_list = """- receipt: Purchase confirmation, order receipt, invoice, payment confirmation
- shipping: Shipping notification, delivery update, tracking info
- account_security: Password reset, login alert, 2FA, security warning
- promotional: Marketing, sale, discount, promotional offer
- newsletter: Newsletter, digest, weekly/daily update
- personal: Personal message, direct communication
- other: Does not fit other categories"""

    prompt = f"""Analyze these {len(emails)} emails and categorize each based on CONTENT, not just sender.

{all_emails_text}

**Available Content Categories:**
{categories_list}

**Response Format (JSON array, one object per email):**
[
  {{"email_id": "id1", "content_category": "category", "importance": "high/medium/low", "contains_receipt": true/false, "contains_tracking": true/false, "requires_action": true/false, "key_info": "brief summary"}},
  ...
]

IMPORTANT: Use ONLY the categories listed above. If an email doesn't fit any specific category, use "other".

Respond with valid JSON array only, no other text."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    return {
        'format': 'JSON',
        'prompt': prompt,
        'response': response.content[0].text,
        'input_tokens': response.usage.input_tokens,
        'output_tokens': response.usage.output_tokens,
        'total_tokens': response.usage.input_tokens + response.usage.output_tokens
    }


def main():
    if not ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY not set")
        return

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    categories = load_categories()

    print("Fetching 10 random emails...")
    emails = get_10_random_emails()
    print(f"Got {len(emails)} emails\n")

    # Test both formats
    print("Testing COMPACT format...")
    compact = test_compact_format(client, emails, categories)

    print("Testing JSON format...")
    json_fmt = test_json_format(client, emails, categories)

    # Print FULL results
    print("\n")
    print("=" * 80)
    print("=" * 80)
    print("COMPACT FORMAT - FULL INPUT PROMPT")
    print("=" * 80)
    print("=" * 80)
    print(compact['prompt'])

    print("\n")
    print("=" * 80)
    print("=" * 80)
    print("COMPACT FORMAT - FULL OUTPUT RESPONSE")
    print("=" * 80)
    print("=" * 80)
    print(compact['response'])

    print("\n")
    print("=" * 80)
    print("=" * 80)
    print("JSON FORMAT - FULL INPUT PROMPT")
    print("=" * 80)
    print("=" * 80)
    print(json_fmt['prompt'])

    print("\n")
    print("=" * 80)
    print("=" * 80)
    print("JSON FORMAT - FULL OUTPUT RESPONSE")
    print("=" * 80)
    print("=" * 80)
    print(json_fmt['response'])

    # Token comparison
    print("\n")
    print("=" * 80)
    print("=" * 80)
    print("TOKEN COMPARISON")
    print("=" * 80)
    print("=" * 80)

    print(f"\n{'Metric':<20} {'COMPACT':>15} {'JSON':>15} {'Savings':>15}")
    print("-" * 65)
    print(f"{'Input tokens':<20} {compact['input_tokens']:>15,} {json_fmt['input_tokens']:>15,} {json_fmt['input_tokens'] - compact['input_tokens']:>15,}")
    print(f"{'Output tokens':<20} {compact['output_tokens']:>15,} {json_fmt['output_tokens']:>15,} {json_fmt['output_tokens'] - compact['output_tokens']:>15,}")
    print(f"{'Total tokens':<20} {compact['total_tokens']:>15,} {json_fmt['total_tokens']:>15,} {json_fmt['total_tokens'] - compact['total_tokens']:>15,}")

    if json_fmt['total_tokens'] > 0:
        savings_pct = (1 - compact['total_tokens'] / json_fmt['total_tokens']) * 100
        print(f"\nTotal savings: {savings_pct:.1f}%")

    output_savings_pct = (1 - compact['output_tokens'] / json_fmt['output_tokens']) * 100 if json_fmt['output_tokens'] > 0 else 0
    print(f"Output token savings: {output_savings_pct:.1f}%")


if __name__ == "__main__":
    main()
