"""Unit tests for progress event dataclasses and the generator methods that yield them.

Covers:
- CategorizeProgress: field values, sequencing, error fallback, batch splitting
- OrganizeProgress: field values, success/failure, dry-run, missing label
- DeleteProgress: field values, success/failure, dry-run

Run from project root:
    python -m unittest tests/unit/test_progress_events.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from services.email_service import (
    EmailService,
    CategorizeProgress,
    OrganizeProgress,
    DeleteProgress,
    ProgressEvent,
)
from providers.base import Email


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_email(email_id="id-1", subject="Test Subject", body="body"):
    return Email(
        id=email_id,
        subject=subject,
        sender="sender@example.com",
        recipient="me@example.com",
        body=body,
        html_body=None,
        received_date=datetime(2026, 1, 1),
        has_attachments=False,
        is_read=False,
        labels=[],
    )


def make_email_dict(email_id="id-1", subject="Test Subject", category="newsletter"):
    return {
        'id': email_id,
        'subject': subject,
        'sender': 'sender@example.com',
        'recipient': 'me@example.com',
        'body': 'body',
        'html_body': None,
        'received_date': '2026-01-01T00:00:00',
        'has_attachments': False,
        'is_read': False,
        'labels': [],
        'category': category,
    }


CATEGORIES = {
    'urgent': 'Requires immediate action',
    'newsletter': 'Marketing content',
    'other': 'Does not fit other categories',
}


def make_service(cache=None):
    if cache is None:
        cache = MagicMock()
    return EmailService(cache, CATEGORIES)


# ---------------------------------------------------------------------------
# ProgressEvent base
# ---------------------------------------------------------------------------

class TestProgressEventBase(unittest.TestCase):

    def test_categorize_progress_is_progress_event(self):
        event = CategorizeProgress(index=1, total=5, subject="Sub", category="urgent")
        self.assertIsInstance(event, ProgressEvent)

    def test_organize_progress_is_progress_event(self):
        event = OrganizeProgress(index=1, total=5, subject="Sub", category="newsletter", success=True)
        self.assertIsInstance(event, ProgressEvent)

    def test_delete_progress_is_progress_event(self):
        event = DeleteProgress(index=1, total=5, subject="Sub", success=True)
        self.assertIsInstance(event, ProgressEvent)


# ---------------------------------------------------------------------------
# categorize_emails
# ---------------------------------------------------------------------------

class TestCategorizeEmails(unittest.TestCase):

    def _make_categorizer(self, results: dict) -> MagicMock:
        cat = MagicMock()
        cat.batch_categorize.return_value = results
        return cat

    def test_yields_categorize_progress_instances(self):
        cache = MagicMock()
        cache.get_uncategorized_emails.return_value = [make_email("id-1")]
        cache.update_category.return_value = None
        service = make_service(cache)
        categorizer = self._make_categorizer({"id-1": {"category": "urgent", "reasoning": ""}})

        events = list(service.categorize_emails(categorizer, limit=10))

        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], CategorizeProgress)

    def test_event_fields_match_email(self):
        cache = MagicMock()
        cache.get_uncategorized_emails.return_value = [make_email("id-1", subject="My Email")]
        cache.update_category.return_value = None
        service = make_service(cache)
        categorizer = self._make_categorizer({"id-1": {"category": "newsletter", "reasoning": ""}})

        events = list(service.categorize_emails(categorizer, limit=10))

        self.assertEqual(events[0].subject, "My Email")
        self.assertEqual(events[0].category, "newsletter")
        self.assertEqual(events[0].index, 1)
        self.assertEqual(events[0].total, 1)

    def test_index_increments_sequentially(self):
        emails = [make_email(f"id-{i}", f"Subject {i}") for i in range(3)]
        cache = MagicMock()
        cache.get_uncategorized_emails.return_value = emails
        cache.update_category.return_value = None
        service = make_service(cache)
        results = {f"id-{i}": {"category": "other", "reasoning": ""} for i in range(3)}
        categorizer = self._make_categorizer(results)

        events = list(service.categorize_emails(categorizer, limit=10))

        self.assertEqual([e.index for e in events], [1, 2, 3])
        self.assertEqual(events[0].total, 3)
        self.assertEqual(events[2].total, 3)

    def test_cache_error_yields_error_category(self):
        cache = MagicMock()
        cache.get_uncategorized_emails.return_value = [make_email("id-1")]
        cache.update_category.side_effect = Exception("DB error")
        service = make_service(cache)
        categorizer = self._make_categorizer({"id-1": {"category": "urgent", "reasoning": ""}})

        events = list(service.categorize_emails(categorizer, limit=10))

        self.assertEqual(events[0].category, "ERROR")

    def test_batch_api_error_yields_other_category(self):
        emails = [make_email(f"id-{i}") for i in range(2)]
        cache = MagicMock()
        cache.get_uncategorized_emails.return_value = emails
        cache.update_category.return_value = None
        service = make_service(cache)
        categorizer = MagicMock()
        categorizer.batch_categorize.side_effect = Exception("API down")

        events = list(service.categorize_emails(categorizer, limit=10))

        self.assertEqual(len(events), 2)
        for event in events:
            self.assertEqual(event.category, "other")

    def test_yields_nothing_when_no_emails(self):
        cache = MagicMock()
        cache.get_uncategorized_emails.return_value = []
        service = make_service(cache)
        categorizer = MagicMock()

        events = list(service.categorize_emails(categorizer, limit=10))

        self.assertEqual(events, [])


# ---------------------------------------------------------------------------
# organize_emails
# ---------------------------------------------------------------------------

class TestOrganizeEmails(unittest.TestCase):

    def _make_gmail(self, label_map=None, apply_success=True):
        gmail = MagicMock()
        gmail.ensure_labels.return_value = {"Newsletter": "label-id-1"} if label_map is None else label_map
        gmail.apply_category_label.return_value = apply_success
        return gmail

    def _emails(self, count=2, category="newsletter"):
        return [make_email_dict(f"id-{i}", f"Subject {i}", category) for i in range(count)]

    def test_yields_organize_progress_instances(self):
        cache = MagicMock()
        cache.get_emails.return_value = self._emails(1)
        service = make_service(cache)
        gmail = self._make_gmail()

        with patch("config.category_to_folder", return_value="Newsletter"):
            events = list(service.organize_emails(gmail, category="newsletter", limit=10))

        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], OrganizeProgress)

    def test_success_field_true_on_successful_apply(self):
        cache = MagicMock()
        cache.get_emails.return_value = self._emails(1)
        service = make_service(cache)
        gmail = self._make_gmail(apply_success=True)

        with patch("config.category_to_folder", return_value="Newsletter"):
            events = list(service.organize_emails(gmail, category="newsletter", limit=10))

        self.assertTrue(events[0].success)

    def test_success_field_false_on_failed_apply(self):
        cache = MagicMock()
        cache.get_emails.return_value = self._emails(1)
        service = make_service(cache)
        gmail = self._make_gmail(apply_success=False)

        with patch("config.category_to_folder", return_value="Newsletter"):
            events = list(service.organize_emails(gmail, category="newsletter", limit=10))

        self.assertFalse(events[0].success)

    def test_dry_run_does_not_call_gmail_api(self):
        cache = MagicMock()
        cache.get_emails.return_value = self._emails(2)
        service = make_service(cache)
        gmail = MagicMock()

        with patch("config.category_to_folder", return_value="Newsletter"):
            events = list(service.organize_emails(gmail, dry_run=True, limit=10))

        gmail.apply_category_label.assert_not_called()
        self.assertTrue(all(e.success for e in events))

    def test_missing_label_yields_success_false(self):
        cache = MagicMock()
        cache.get_emails.return_value = self._emails(1, category="newsletter")
        service = make_service(cache)
        # ensure_labels returns empty — no label for this category
        gmail = self._make_gmail(label_map={})

        with patch("config.category_to_folder", return_value="Newsletter"):
            events = list(service.organize_emails(gmail, category="newsletter", limit=10))

        self.assertFalse(events[0].success)

    def test_event_fields(self):
        cache = MagicMock()
        cache.get_emails.return_value = [make_email_dict("id-1", "My Subject", "newsletter")]
        service = make_service(cache)
        gmail = self._make_gmail()

        with patch("config.category_to_folder", return_value="Newsletter"):
            events = list(service.organize_emails(gmail, category="newsletter", limit=10))

        self.assertEqual(events[0].subject, "My Subject")
        self.assertEqual(events[0].category, "newsletter")
        self.assertEqual(events[0].index, 1)
        self.assertEqual(events[0].total, 1)

    def test_yields_nothing_when_no_emails(self):
        cache = MagicMock()
        cache.get_emails.return_value = []
        service = make_service(cache)

        events = list(service.organize_emails(MagicMock(), limit=10))

        self.assertEqual(events, [])


# ---------------------------------------------------------------------------
# delete_emails_by_category
# ---------------------------------------------------------------------------

class TestDeleteEmailsByCategory(unittest.TestCase):

    def _emails(self, count=2, category="newsletter"):
        return [make_email_dict(f"id-{i}", f"Subject {i}", category) for i in range(count)]

    def test_yields_delete_progress_instances(self):
        cache = MagicMock()
        cache.get_emails.return_value = self._emails(1)
        service = make_service(cache)
        gmail = MagicMock()
        gmail.delete_email.return_value = True

        events = list(service.delete_emails_by_category(gmail, category="newsletter", limit=10))

        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], DeleteProgress)

    def test_success_field_true_on_successful_delete(self):
        cache = MagicMock()
        cache.get_emails.return_value = self._emails(1)
        service = make_service(cache)
        gmail = MagicMock()
        gmail.delete_email.return_value = True

        events = list(service.delete_emails_by_category(gmail, category="newsletter", limit=10))

        self.assertTrue(events[0].success)

    def test_success_field_false_on_failed_delete(self):
        cache = MagicMock()
        cache.get_emails.return_value = self._emails(1)
        service = make_service(cache)
        gmail = MagicMock()
        gmail.delete_email.return_value = False

        events = list(service.delete_emails_by_category(gmail, category="newsletter", limit=10))

        self.assertFalse(events[0].success)

    def test_dry_run_does_not_call_gmail_api(self):
        cache = MagicMock()
        cache.get_emails.return_value = self._emails(2)
        service = make_service(cache)
        gmail = MagicMock()

        events = list(service.delete_emails_by_category(
            gmail, category="newsletter", limit=10, dry_run=True
        ))

        gmail.delete_email.assert_not_called()
        self.assertTrue(all(e.success for e in events))

    def test_event_fields(self):
        cache = MagicMock()
        cache.get_emails.return_value = [make_email_dict("id-1", "My Subject", "newsletter")]
        service = make_service(cache)
        gmail = MagicMock()
        gmail.delete_email.return_value = True

        events = list(service.delete_emails_by_category(gmail, category="newsletter", limit=10))

        self.assertEqual(events[0].subject, "My Subject")
        self.assertEqual(events[0].index, 1)
        self.assertEqual(events[0].total, 1)

    def test_index_increments_sequentially(self):
        cache = MagicMock()
        cache.get_emails.return_value = self._emails(3)
        service = make_service(cache)
        gmail = MagicMock()
        gmail.delete_email.return_value = True

        events = list(service.delete_emails_by_category(gmail, category="newsletter", limit=10))

        self.assertEqual([e.index for e in events], [1, 2, 3])
        self.assertTrue(all(e.total == 3 for e in events))

    def test_yields_nothing_when_no_emails(self):
        cache = MagicMock()
        cache.get_emails.return_value = []
        service = make_service(cache)

        events = list(service.delete_emails_by_category(MagicMock(), category="newsletter", limit=10))

        self.assertEqual(events, [])

    def test_permanent_flag_passed_to_gmail(self):
        cache = MagicMock()
        cache.get_emails.return_value = self._emails(1)
        service = make_service(cache)
        gmail = MagicMock()
        gmail.delete_email.return_value = True

        list(service.delete_emails_by_category(
            gmail, category="newsletter", limit=10, permanent=True
        ))

        gmail.delete_email.assert_called_once_with("id-0", permanent=True)


if __name__ == "__main__":
    unittest.main()
