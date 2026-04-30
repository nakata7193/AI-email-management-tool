#!/usr/bin/env python3
"""Test different batch sizes to find optimal configuration.

Tests: 10, 50, 100, 200, 400, 1000 emails per batch
Measures: tokens consumed, time taken, cost estimate
Results are saved to tests/results/

Run from project root: python3 tests/test_batch_sizes.py
"""

import sqlite3
import os
import json
import time
from datetime import datetime
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# Paths relative to project root (run from project root)
DB_PATH = "email_cache_atanas.db"
RESULTS_DIR = "tests/results"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Pricing for Claude Sonnet 4.6 (per 1M tokens)
INPUT_PRICE_PER_M = 3.0   # $3 per 1M input tokens
OUTPUT_PRICE_PER_M = 15.0  # $15 per 1M output tokens


def get_random_emails(count):
    """Get random analyzed emails."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, subject, sender, body
        FROM emails
        WHERE ai_analyzed = 1
        ORDER BY RANDOM()
        LIMIT ?
    """, (count,))
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


def build_prompt(emails, categories):
    """Build the compact prompt for a batch of emails."""
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

    return prompt


def test_batch(client, emails, categories):
    """Test a single batch and return metrics."""
    prompt = build_prompt(emails, categories)

    start_time = time.time()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=len(emails) * 20,  # ~20 tokens per line output
        messages=[{"role": "user", "content": prompt}]
    )
    elapsed = time.time() - start_time

    return {
        'input_tokens': response.usage.input_tokens,
        'output_tokens': response.usage.output_tokens,
        'time': elapsed,
        'response': response.content[0].text
    }


def run_batch_test(client, all_emails, batch_size, categories):
    """Process all emails with given batch size and measure totals."""
    total_input = 0
    total_output = 0
    total_time = 0
    num_batches = 0

    for i in range(0, len(all_emails), batch_size):
        batch = all_emails[i:i + batch_size]
        result = test_batch(client, batch, categories)

        total_input += result['input_tokens']
        total_output += result['output_tokens']
        total_time += result['time']
        num_batches += 1

        print(f"    Batch {num_batches}: {len(batch)} emails, {result['input_tokens']} in, {result['output_tokens']} out, {result['time']:.2f}s")

    return {
        'batch_size': batch_size,
        'num_batches': num_batches,
        'total_input': total_input,
        'total_output': total_output,
        'total_tokens': total_input + total_output,
        'total_time': total_time,
        'input_cost': (total_input / 1_000_000) * INPUT_PRICE_PER_M,
        'output_cost': (total_output / 1_000_000) * OUTPUT_PRICE_PER_M,
    }


def main():
    if not ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY not set")
        return

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    categories = load_categories()

    # Get 1000 random emails
    total_emails = 1000
    print(f"Fetching {total_emails} random emails...")
    all_emails = get_random_emails(total_emails)
    print(f"Got {len(all_emails)} emails\n")

    # Test different batch sizes
    batch_sizes = [10, 50, 100, 200, 400, 1000]
    results = []

    for batch_size in batch_sizes:
        print(f"\n{'='*60}")
        print(f"Testing batch size: {batch_size}")
        print(f"{'='*60}")

        result = run_batch_test(client, all_emails, batch_size, categories)
        results.append(result)

        print(f"\n  Summary for batch_size={batch_size}:")
        print(f"    API calls:     {result['num_batches']}")
        print(f"    Total time:    {result['total_time']:.2f}s")
        print(f"    Input tokens:  {result['total_input']:,}")
        print(f"    Output tokens: {result['total_output']:,}")
        print(f"    Total tokens:  {result['total_tokens']:,}")
        print(f"    Est. cost:     ${result['input_cost'] + result['output_cost']:.4f}")

    # Final comparison
    print("\n")
    print("=" * 80)
    print("FINAL COMPARISON - 1000 EMAILS")
    print("=" * 80)
    print(f"\n{'Batch':<8} {'Calls':<8} {'Time(s)':<10} {'Input':<12} {'Output':<10} {'Total':<12} {'Cost($)':<10}")
    print("-" * 80)

    for r in results:
        total_cost = r['input_cost'] + r['output_cost']
        print(f"{r['batch_size']:<8} {r['num_batches']:<8} {r['total_time']:<10.2f} {r['total_input']:<12,} {r['total_output']:<10,} {r['total_tokens']:<12,} {total_cost:<10.4f}")

    # Find optimal
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    fastest = min(results, key=lambda x: x['total_time'])
    cheapest = min(results, key=lambda x: x['input_cost'] + x['output_cost'])

    print(f"\nFastest:  batch_size={fastest['batch_size']} ({fastest['total_time']:.2f}s, {fastest['num_batches']} API calls)")
    print(f"Cheapest: batch_size={cheapest['batch_size']} (${cheapest['input_cost'] + cheapest['output_cost']:.4f})")

    # Save results to file
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"batch_sizes_{timestamp}.txt")

    with open(result_file, 'w') as f:
        f.write(f"BATCH SIZE COMPARISON TEST RESULTS\n")
        f.write(f"===================================\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Emails tested: {total_emails}\n\n")
        f.write(f"{'Batch':<8} {'Calls':<8} {'Time(s)':<10} {'Input':<12} {'Output':<10} {'Total':<12} {'Cost($)':<10}\n")
        f.write("-" * 80 + "\n")
        for r in results:
            total_cost = r['input_cost'] + r['output_cost']
            f.write(f"{r['batch_size']:<8} {r['num_batches']:<8} {r['total_time']:<10.2f} {r['total_input']:<12,} {r['total_output']:<10,} {r['total_tokens']:<12,} {total_cost:<10.4f}\n")
        f.write(f"\nFastest:  batch_size={fastest['batch_size']} ({fastest['total_time']:.2f}s)\n")
        f.write(f"Cheapest: batch_size={cheapest['batch_size']} (${cheapest['input_cost'] + cheapest['output_cost']:.4f})\n")

    print(f"\nResults saved to: {result_file}")


if __name__ == "__main__":
    main()
