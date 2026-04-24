"""Email parser utilities for extracting and cleaning email content."""

from bs4 import BeautifulSoup
import html2text
from typing import Optional
import re

class EmailParser:
    """Utility class for parsing and cleaning email content."""

    def __init__(self):
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True
        self.html_converter.ignore_emphasis = False
        self.html_converter.body_width = 0  # Don't wrap lines

    def html_to_text(self, html_content: str) -> str:
        """
        Convert HTML email content to clean plain text.

        Args:
            html_content: Raw HTML string

        Returns:
            Cleaned plain text version
        """
        if not html_content:
            return ""

        try:
            # First pass: BeautifulSoup for basic cleaning
            soup = BeautifulSoup(html_content, 'lxml')

            # Remove script and style elements
            for element in soup(['script', 'style', 'head', 'title']):
                element.decompose()

            # Convert to markdown-style text
            text = self.html_converter.handle(str(soup))

            # Clean up excessive whitespace
            text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
            text = text.strip()

            return text

        except Exception as e:
            # Fallback to simple text extraction
            try:
                soup = BeautifulSoup(html_content, 'lxml')
                return soup.get_text(separator='\n', strip=True)
            except:
                return html_content

    def extract_quoted_reply(self, email_body: str) -> tuple[str, Optional[str]]:
        """
        Separate the new message from quoted replies.

        Args:
            email_body: Full email body text

        Returns:
            Tuple of (new_content, quoted_content)
        """
        # Common quote indicators
        quote_patterns = [
            r'On .* wrote:',
            r'From:.*\nSent:.*\nTo:.*\nSubject:',
            r'-----Original Message-----',
            r'________________________________',
            r'Begin forwarded message:',
        ]

        for pattern in quote_patterns:
            match = re.search(pattern, email_body, re.IGNORECASE | re.MULTILINE)
            if match:
                split_pos = match.start()
                new_content = email_body[:split_pos].strip()
                quoted_content = email_body[split_pos:].strip()
                return new_content, quoted_content

        # No quotes found
        return email_body, None

    def clean_text(self, text: str) -> str:
        """
        Clean and normalize text content.

        Args:
            text: Raw text string

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove excessive whitespace
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)

        # Remove common email artifacts
        text = re.sub(r'\[cid:.*?\]', '', text)  # Remove inline image references
        text = re.sub(r'<.*?>', '', text)  # Remove any remaining HTML tags

        return text.strip()

    def extract_signature(self, email_body: str) -> tuple[str, Optional[str]]:
        """
        Attempt to separate email body from signature.

        Args:
            email_body: Full email body

        Returns:
            Tuple of (body_without_signature, signature)
        """
        # Common signature delimiters
        signature_patterns = [
            r'^--\s*$',  # Standard signature delimiter
            r'^— \s*$',
            r'^Sent from my iPhone$',
            r'^Sent from my Android',
            r'^Get Outlook for',
        ]

        lines = email_body.split('\n')

        for i, line in enumerate(lines):
            for pattern in signature_patterns:
                if re.match(pattern, line.strip(), re.IGNORECASE):
                    body = '\n'.join(lines[:i]).strip()
                    signature = '\n'.join(lines[i:]).strip()
                    return body, signature

        return email_body, None

    def truncate_for_ai(self, text: str, max_chars: int = 10000) -> str:
        """
        Truncate text to a reasonable length for AI processing.

        Args:
            text: Input text
            max_chars: Maximum character count

        Returns:
            Truncated text with indicator if truncated
        """
        if len(text) <= max_chars:
            return text

        truncated = text[:max_chars].rsplit(' ', 1)[0]  # Don't cut mid-word
        return truncated + "\n\n[... truncated for length ...]"

    def extract_urls(self, text: str) -> list[str]:
        """
        Extract URLs from text.

        Args:
            text: Input text

        Returns:
            List of URLs found
        """
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, text)
        return list(set(urls))  # Remove duplicates

    def get_text_preview(self, text: str, length: int = 200) -> str:
        """
        Get a preview of text content.

        Args:
            text: Input text
            length: Preview length in characters

        Returns:
            Text preview
        """
        if not text:
            return ""

        text = self.clean_text(text)

        if len(text) <= length:
            return text

        preview = text[:length].rsplit(' ', 1)[0]
        return preview + "..."
