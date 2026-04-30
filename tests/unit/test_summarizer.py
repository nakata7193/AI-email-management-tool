"""Unit tests for EmailSummarizer.

Run from project root:
    python -m unittest tests/test_summarizer.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from datetime import datetime
from unittest.mock import MagicMock

from ai.summarizer import EmailSummarizer
from parsers.email_parser import EmailContentPreparer
from providers.base import Email


def make_email(
    email_id="test-id-1",
    subject="Test Subject",
    sender="sender@example.com",
    body="Body text",
    html_body=None,
    received_date=None,
):
    return Email(
        id=email_id,
        subject=subject,
        sender=sender,
        recipient="me@example.com",
        body=body,
        html_body=html_body,
        received_date=received_date or datetime(2026, 1, 15),
        has_attachments=False,
        is_read=False,
        labels=[],
    )


class TestEmailSummarizerSummarize(unittest.TestCase):

    def _make_summarizer(self, ai_response: str) -> EmailSummarizer:
        client = MagicMock()
        client.complete.return_value = ai_response
        preparer = EmailContentPreparer()
        return EmailSummarizer(client, preparer)

    def test_parses_summary_and_action_items(self):
        summ = self._make_summarizer(
            "Summary: The email discusses a meeting.\nAction Items: Schedule follow-up"
        )
        result = summ.summarize(make_email())
        self.assertEqual(result['summary'], 'The email discusses a meeting.')
        self.assertEqual(result['action_items'], 'Schedule follow-up')

    def test_fallback_when_no_structured_response(self):
        summ = self._make_summarizer("Just a plain summary with no markers.")
        result = summ.summarize(make_email())
        self.assertEqual(result['summary'], "Just a plain summary with no markers.")
        self.assertEqual(result['action_items'], '')

    def test_ai_error_returns_error_message(self):
        client = MagicMock()
        client.complete.side_effect = Exception("API error")
        summ = EmailSummarizer(client, EmailContentPreparer())
        result = summ.summarize(make_email())
        self.assertIn('Error', result['summary'])
        self.assertEqual(result['action_items'], '')

    def test_prompt_contains_subject_sender_recipient(self):
        client = MagicMock()
        client.complete.return_value = "Summary: ok\nAction Items: None"
        summ = EmailSummarizer(client, EmailContentPreparer())
        summ.summarize(make_email(subject="Budget Q1", sender="cfo@corp.com"))
        prompt = client.complete.call_args[0][0]
        self.assertIn("Budget Q1", prompt)
        self.assertIn("cfo@corp.com", prompt)

    def test_uses_8000_char_budget(self):
        client = MagicMock()
        client.complete.return_value = "Summary: ok\nAction Items: None"
        preparer = MagicMock()
        preparer.prepare.return_value = "PREPARED"
        summ = EmailSummarizer(client, preparer)
        summ.summarize(make_email(body="raw body", html_body="<html>x</html>"))
        preparer.prepare.assert_called_once_with("raw body", "<html>x</html>", max_chars=8000)

    def test_action_items_section_included_by_default(self):
        client = MagicMock()
        client.complete.return_value = "Summary: ok\nAction Items: None"
        summ = EmailSummarizer(client, EmailContentPreparer())
        summ.summarize(make_email())
        prompt = client.complete.call_args[0][0]
        self.assertIn("Action Items", prompt)

    def test_action_items_section_excluded_when_disabled(self):
        client = MagicMock()
        client.complete.return_value = "Summary: ok\nAction Items: None"
        summ = EmailSummarizer(client, EmailContentPreparer())
        summ.summarize(make_email(), include_action_items=False)
        prompt = client.complete.call_args[0][0]
        # The instructions block ("3. Action Items:") is excluded;
        # only the response format line remains which is always present
        self.assertNotIn("3. Action Items", prompt)


class TestEmailSummarizerThread(unittest.TestCase):

    def test_empty_thread_returns_message(self):
        client = MagicMock()
        summ = EmailSummarizer(client, EmailContentPreparer())
        result = summ.summarize_thread([])
        self.assertEqual(result, "Empty thread")

    def test_single_email_thread_delegates_to_summarize(self):
        client = MagicMock()
        client.complete.return_value = "Summary: Single email summary.\nAction Items: None"
        summ = EmailSummarizer(client, EmailContentPreparer())
        result = summ.summarize_thread([make_email()])
        self.assertIn("Single email summary", result)

    def test_multi_email_thread_calls_ai_once(self):
        client = MagicMock()
        client.complete.return_value = "Thread covers a project discussion."
        summ = EmailSummarizer(client, EmailContentPreparer())
        emails = [make_email(email_id=f"id-{i}") for i in range(3)]
        summ.summarize_thread(emails)
        # One call for the thread summary (not one per email)
        self.assertEqual(client.complete.call_count, 1)

    def test_thread_prompt_includes_sender_and_date(self):
        client = MagicMock()
        client.complete.return_value = "Thread summary."
        summ = EmailSummarizer(client, EmailContentPreparer())
        emails = [
            make_email(sender="alice@example.com", received_date=datetime(2026, 3, 1)),
            make_email(sender="bob@example.com", received_date=datetime(2026, 3, 2)),
        ]
        summ.summarize_thread(emails)
        prompt = client.complete.call_args[0][0]
        self.assertIn("alice@example.com", prompt)
        self.assertIn("bob@example.com", prompt)
        self.assertIn("2026-03-01", prompt)

    def test_thread_uses_500_char_budget_per_email(self):
        client = MagicMock()
        client.complete.return_value = "Thread summary."
        preparer = MagicMock()
        preparer.prepare.return_value = "PREVIEW"
        summ = EmailSummarizer(client, preparer)
        emails = [make_email(body="body1"), make_email(body="body2")]
        summ.summarize_thread(emails)
        calls = preparer.prepare.call_args_list
        for call in calls:
            self.assertEqual(call.kwargs.get('max_chars') or call[1].get('max_chars') or call[0][2], 500)

    def test_thread_error_returns_error_message(self):
        client = MagicMock()
        client.complete.side_effect = Exception("API down")
        summ = EmailSummarizer(client, EmailContentPreparer())
        result = summ.summarize_thread([make_email(), make_email()])
        self.assertIn("Error", result)


class TestEmailSummarizerResponseSuggestion(unittest.TestCase):

    def test_returns_suggestion(self):
        client = MagicMock()
        client.complete.return_value = "Thank you for your email."
        summ = EmailSummarizer(client, EmailContentPreparer())
        result = summ.generate_response_suggestion(make_email())
        self.assertEqual(result, "Thank you for your email.")

    def test_uses_3000_char_budget(self):
        client = MagicMock()
        client.complete.return_value = "Reply text."
        preparer = MagicMock()
        preparer.prepare.return_value = "PREPARED"
        summ = EmailSummarizer(client, preparer)
        summ.generate_response_suggestion(make_email(body="raw", html_body="<html>x</html>"))
        preparer.prepare.assert_called_once_with("raw", "<html>x</html>", max_chars=3000)

    def test_prompt_includes_subject_and_sender(self):
        client = MagicMock()
        client.complete.return_value = "Reply text."
        summ = EmailSummarizer(client, EmailContentPreparer())
        summ.generate_response_suggestion(make_email(subject="Proposal", sender="client@biz.com"))
        prompt = client.complete.call_args[0][0]
        self.assertIn("Proposal", prompt)
        self.assertIn("client@biz.com", prompt)

    def test_empty_ai_response_returns_fallback(self):
        client = MagicMock()
        client.complete.return_value = ""
        summ = EmailSummarizer(client, EmailContentPreparer())
        result = summ.generate_response_suggestion(make_email())
        self.assertEqual(result, "Could not generate response")

    def test_ai_error_returns_error_message(self):
        client = MagicMock()
        client.complete.side_effect = Exception("API timeout")
        summ = EmailSummarizer(client, EmailContentPreparer())
        result = summ.generate_response_suggestion(make_email())
        self.assertIn("Error", result)


if __name__ == "__main__":
    unittest.main()
