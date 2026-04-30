"""Unit tests for EmailCategorizer.

Run from project root:
    python -m unittest tests/test_categorizer.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from datetime import datetime
from unittest.mock import MagicMock

from ai.categorizer import EmailCategorizer
from ai.client import MockAIClient
from parsers.email_parser import EmailContentPreparer
from providers.base import Email

CATEGORIES = {
    'urgent': 'Requires immediate action',
    'newsletter': 'Marketing or subscription content',
    'receipts': 'Purchase confirmations',
    'other': 'Does not fit other categories',
}


def make_email(subject="Test", sender="sender@example.com", body="Body text", html_body=None):
    return Email(
        id="test-id-1",
        subject=subject,
        sender=sender,
        recipient="me@example.com",
        body=body,
        html_body=html_body,
        received_date=datetime(2026, 1, 1),
        has_attachments=False,
        is_read=False,
        labels=[],
    )


class TestEmailCategorizerCategorize(unittest.TestCase):

    def _make_categorizer(self, ai_response: str) -> EmailCategorizer:
        client = MagicMock()
        client.complete.return_value = ai_response
        preparer = EmailContentPreparer()
        cat = EmailCategorizer(client, preparer)
        cat._get_categories = MagicMock(return_value=CATEGORIES)
        return cat

    def test_returns_valid_category(self):
        cat = self._make_categorizer("Category: urgent\nReasoning: Action needed")
        result = cat.categorize(make_email())
        self.assertEqual(result['category'], 'urgent')

    def test_returns_reasoning(self):
        cat = self._make_categorizer("Category: newsletter\nReasoning: Bulk marketing email")
        result = cat.categorize(make_email())
        self.assertEqual(result['reasoning'], 'Bulk marketing email')

    def test_unknown_category_falls_back_to_first(self):
        cat = self._make_categorizer("Category: nonexistent\nReasoning: Something")
        result = cat.categorize(make_email())
        self.assertEqual(result['category'], 'urgent')  # first key in CATEGORIES

    def test_missing_reasoning_returns_default(self):
        cat = self._make_categorizer("Category: receipts")
        result = cat.categorize(make_email())
        self.assertEqual(result['reasoning'], 'No reasoning provided')

    def test_ai_error_returns_fallback(self):
        client = MagicMock()
        client.complete.side_effect = Exception("API error")
        preparer = EmailContentPreparer()
        cat = EmailCategorizer(client, preparer)
        cat._get_categories = MagicMock(return_value=CATEGORIES)
        result = cat.categorize(make_email())
        self.assertIn(result['category'], CATEGORIES)
        self.assertIn('Error', result['reasoning'])

    def test_prompt_contains_subject_and_sender(self):
        client = MagicMock()
        client.complete.return_value = "Category: other\nReasoning: test"
        preparer = EmailContentPreparer()
        cat = EmailCategorizer(client, preparer)
        cat._get_categories = MagicMock(return_value=CATEGORIES)
        cat.categorize(make_email(subject="My Subject", sender="boss@corp.com"))
        prompt = client.complete.call_args[0][0]
        self.assertIn("My Subject", prompt)
        self.assertIn("boss@corp.com", prompt)

    def test_prompt_contains_prepared_body(self):
        client = MagicMock()
        client.complete.return_value = "Category: other\nReasoning: test"
        preparer = MagicMock()
        preparer.prepare.return_value = "PREPARED_BODY"
        cat = EmailCategorizer(client, preparer)
        cat._get_categories = MagicMock(return_value=CATEGORIES)
        cat.categorize(make_email(body="raw body"))
        preparer.prepare.assert_called_once_with("raw body", None, max_chars=5000)
        prompt = client.complete.call_args[0][0]
        self.assertIn("PREPARED_BODY", prompt)

    def test_uses_html_body_via_preparer(self):
        client = MagicMock()
        client.complete.return_value = "Category: other\nReasoning: test"
        preparer = MagicMock()
        preparer.prepare.return_value = "HTML_PREPARED"
        cat = EmailCategorizer(client, preparer)
        cat._get_categories = MagicMock(return_value=CATEGORIES)
        cat.categorize(make_email(body="", html_body="<html>HTML</html>"))
        preparer.prepare.assert_called_once_with("", "<html>HTML</html>", max_chars=5000)


class TestEmailCategorizerBatchCategorize(unittest.TestCase):

    def _make_categorizer(self, ai_response: str) -> EmailCategorizer:
        client = MagicMock()
        client.complete.return_value = ai_response
        preparer = EmailContentPreparer()
        cat = EmailCategorizer(client, preparer)
        cat._get_categories = MagicMock(return_value=CATEGORIES)
        return cat

    def test_returns_result_for_every_email(self):
        emails = [make_email() for _ in range(3)]
        emails[0].id = "id-1"
        emails[1].id = "id-2"
        emails[2].id = "id-3"
        cat = self._make_categorizer("1. urgent\n2. newsletter\n3. receipts")
        results = cat.batch_categorize(emails)
        self.assertEqual(set(results.keys()), {"id-1", "id-2", "id-3"})

    def test_maps_categories_by_position(self):
        emails = [make_email() for _ in range(3)]
        emails[0].id = "id-1"
        emails[1].id = "id-2"
        emails[2].id = "id-3"
        cat = self._make_categorizer("1. urgent\n2. newsletter\n3. receipts")
        results = cat.batch_categorize(emails)
        self.assertEqual(results["id-1"]["category"], "urgent")
        self.assertEqual(results["id-2"]["category"], "newsletter")
        self.assertEqual(results["id-3"]["category"], "receipts")

    def test_unknown_category_in_batch_falls_back(self):
        emails = [make_email()]
        emails[0].id = "id-1"
        cat = self._make_categorizer("1. nonexistent_cat")
        results = cat.batch_categorize(emails)
        self.assertIn(results["id-1"]["category"], CATEGORIES)

    def test_missing_line_in_response_falls_back(self):
        emails = [make_email() for _ in range(3)]
        emails[0].id = "id-1"
        emails[1].id = "id-2"
        emails[2].id = "id-3"
        # Response only has 2 lines — third email gets fallback
        cat = self._make_categorizer("1. urgent\n2. newsletter")
        results = cat.batch_categorize(emails)
        self.assertIn(results["id-3"]["category"], CATEGORIES)

    def test_batch_splits_into_chunks_of_100(self):
        emails = [make_email() for _ in range(150)]
        for i, e in enumerate(emails):
            e.id = f"id-{i}"
        response_lines = "\n".join(f"{i+1}. other" for i in range(100))
        client = MagicMock()
        client.complete.return_value = response_lines
        preparer = EmailContentPreparer()
        cat = EmailCategorizer(client, preparer)
        cat._get_categories = MagicMock(return_value=CATEGORIES)
        cat.batch_categorize(emails)
        self.assertEqual(client.complete.call_count, 2)  # 150 emails = 2 batches

    def test_batch_uses_400_char_budget_per_email(self):
        emails = [make_email(body="body")]
        emails[0].id = "id-1"
        client = MagicMock()
        client.complete.return_value = "1. other"
        preparer = MagicMock()
        preparer.prepare.return_value = "BATCH_BODY"
        cat = EmailCategorizer(client, preparer)
        cat._get_categories = MagicMock(return_value=CATEGORIES)
        cat.batch_categorize(emails)
        preparer.prepare.assert_called_once_with("body", None, max_chars=400)

    def test_api_error_in_batch_assigns_fallback_to_whole_batch(self):
        emails = [make_email() for _ in range(3)]
        for i, e in enumerate(emails):
            e.id = f"id-{i}"
        client = MagicMock()
        client.complete.side_effect = Exception("API down")
        preparer = EmailContentPreparer()
        cat = EmailCategorizer(client, preparer)
        cat._get_categories = MagicMock(return_value=CATEGORIES)
        results = cat.batch_categorize(emails)
        for i in range(3):
            self.assertIn(results[f"id-{i}"]["category"], CATEGORIES)
            self.assertIn("error", results[f"id-{i}"]["reasoning"].lower())


if __name__ == "__main__":
    unittest.main()
