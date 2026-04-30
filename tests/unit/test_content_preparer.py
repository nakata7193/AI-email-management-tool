"""Unit tests for EmailContentPreparer and _strip_noise.

Run from project root:
    python -m pytest tests/test_content_preparer.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from parsers.email_parser import EmailContentPreparer, _strip_noise


class TestStripNoise(unittest.TestCase):

    # --- invisible spacer characters ---

    def test_removes_zero_width_no_break_space(self):
        # Spacers between words with no surrounding space are removed, not replaced
        self.assertEqual(_strip_noise("hello\ufeffworld"), "helloworld")

    def test_removes_zero_width_space(self):
        self.assertEqual(_strip_noise("hello\u200bworld"), "helloworld")

    def test_removes_soft_hyphen(self):
        self.assertEqual(_strip_noise("hello\u00adworld"), "helloworld")

    def test_removes_spacer_surrounded_by_spaces(self):
        # When spacers appear with surrounding spaces (typical promo email pattern),
        # the result has a single space after whitespace collapsing
        self.assertEqual(_strip_noise("hello \u200c world"), "hello world")

    def test_removes_repeated_spacers(self):
        # Typical promotional email pattern: subject + wall of spacers
        spacers = "\u200c " * 100
        result = _strip_noise(f"Subject line\n{spacers}\nActual content")
        self.assertIn("Subject line", result)
        self.assertIn("Actual content", result)
        self.assertNotIn("\u200c", result)

    # --- URL stripping ---

    def test_removes_bare_url(self):
        result = _strip_noise("Visit https://tracking.example.com/abc123 for info")
        self.assertNotIn("https://", result)
        self.assertIn("Visit", result)
        self.assertIn("for info", result)

    def test_removes_angle_bracket_url(self):
        result = _strip_noise("Click here <https://example.com/track?id=abc>")
        self.assertNotIn("https://", result)
        self.assertNotIn("<", result)
        self.assertIn("Click here", result)

    def test_removes_paren_url(self):
        result = _strip_noise("Buy now ( https://shop.example.com/item?ref=email )")
        self.assertNotIn("https://", result)
        self.assertIn("Buy now", result)

    def test_keeps_markdown_link_label(self):
        result = _strip_noise("Check the [documentation](https://docs.example.com/guide)")
        self.assertIn("documentation", result)
        self.assertNotIn("https://", result)

    def test_removes_multiple_urls(self):
        text = (
            "Line one https://track1.example.com/a\n"
            "Line two https://track2.example.com/b\n"
            "Line three"
        )
        result = _strip_noise(text)
        self.assertNotIn("https://", result)
        self.assertIn("Line one", result)
        self.assertIn("Line two", result)
        self.assertIn("Line three", result)

    # --- whitespace collapsing ---

    def test_collapses_multiple_spaces(self):
        result = _strip_noise("hello    world")
        self.assertEqual(result, "hello world")

    def test_collapses_triple_newlines(self):
        result = _strip_noise("para one\n\n\n\npara two")
        self.assertEqual(result, "para one\n\npara two")

    def test_strips_leading_trailing_whitespace(self):
        result = _strip_noise("  \n  hello  \n  ")
        self.assertEqual(result, "hello")

    # --- real-world promotional email pattern ---

    def test_promotional_email_surfaces_content(self):
        # Simulates eventim-style body: subject + spacer block + tracking URLs + content
        body = (
            "Wacken Open Air 2026\n"
            + "\u200c " * 80
            + "\nhttps://service.eventim.de/go/14/LONGTRACKINGURL?utm_campaign=test\n"
            "Hallo Atanas, das Wacken Open Air ist ein Festival."
        )
        result = _strip_noise(body)
        self.assertIn("Wacken Open Air 2026", result)
        self.assertIn("Hallo Atanas", result)
        self.assertNotIn("\u200c", result)
        self.assertNotIn("https://", result)
        # Content should now be reachable within first 400 chars
        self.assertIn("Hallo Atanas", result[:400])

    # --- passthrough for clean text ---

    def test_clean_text_unchanged(self):
        text = "Hey there!\n\nJust a normal email with no tracking."
        result = _strip_noise(text)
        self.assertEqual(result, text)


class TestEmailContentPreparer(unittest.TestCase):

    def setUp(self):
        self.preparer = EmailContentPreparer()

    # --- html fallback ---

    def test_uses_plain_body_when_available(self):
        result = self.preparer.prepare(
            body="Plain body text",
            html_body="<html><body>HTML body</body></html>",
            max_chars=500
        )
        self.assertEqual(result, "Plain body text")

    def test_falls_back_to_html_when_body_empty(self):
        result = self.preparer.prepare(
            body="",
            html_body="<html><body><p>HTML content</p></body></html>",
            max_chars=500
        )
        self.assertIn("HTML content", result)

    def test_falls_back_to_html_when_body_none(self):
        result = self.preparer.prepare(
            body=None,
            html_body="<html><body><p>HTML content</p></body></html>",
            max_chars=500
        )
        self.assertIn("HTML content", result)

    def test_returns_empty_string_when_both_empty(self):
        result = self.preparer.prepare(body="", html_body=None, max_chars=500)
        self.assertEqual(result, "")

    # --- noise stripping is applied ---

    def test_strips_spacers_from_body(self):
        body = "Subject\n" + "\u200c " * 50 + "\nContent here"
        result = self.preparer.prepare(body=body, html_body=None, max_chars=5000)
        self.assertNotIn("\u200c", result)
        self.assertIn("Content here", result)

    def test_strips_urls_from_body(self):
        body = "Buy now https://tracking.example.com/abc click here"
        result = self.preparer.prepare(body=body, html_body=None, max_chars=5000)
        self.assertNotIn("https://", result)
        self.assertIn("Buy now", result)

    # --- truncation ---

    def test_truncates_to_max_chars(self):
        body = "word " * 1000  # 5000 chars
        result = self.preparer.prepare(body=body, html_body=None, max_chars=100)
        # truncate_for_ai cuts at last word boundary then appends the marker
        self.assertIn("[... truncated", result)
        # total length is bounded: input budget + marker overhead
        self.assertLessEqual(len(result), 140)

    def test_no_truncation_when_under_limit(self):
        body = "Short email body"
        result = self.preparer.prepare(body=body, html_body=None, max_chars=500)
        self.assertEqual(result, "Short email body")

    # --- noise stripping shrinks content before truncation budget is applied ---

    def test_noise_stripped_before_truncation(self):
        # 200 spacers + short content — without stripping, content would be cut
        # With stripping, content fits comfortably in a 50-char budget
        spacers = "\u200c " * 200
        body = spacers + "Important content"
        result = self.preparer.prepare(body=body, html_body=None, max_chars=50)
        self.assertIn("Important content", result)
        self.assertNotIn("[... truncated", result)

    # --- batch budget (400 chars) surfaces message text ---

    def test_400_char_budget_reaches_content_after_stripping(self):
        body = (
            "Newsletter Title\n"
            + "\u200c " * 100
            + "https://track.example.com/open?id=abc123\n"
            "The actual message starts here and contains useful information."
        )
        result = self.preparer.prepare(body=body, html_body=None, max_chars=400)
        self.assertIn("The actual message", result)


if __name__ == "__main__":
    unittest.main()
