"""Email summarization using Claude API."""

import logging
from typing import Dict
from ai.client import AIClient
from providers.base import Email
from parsers.email_parser import ContentPreparer

logger = logging.getLogger(__name__)


class EmailSummarizer:
    """AI-powered email summarization.

    Separates business logic (prompt building, parsing) from I/O (API calls).
    AI client and content preparer are injected, making this class easy to
    test and provider-agnostic.
    """

    def __init__(self, ai_client: AIClient, preparer: ContentPreparer):
        """Initialize summarizer with AI client and content preparer.

        Args:
            ai_client: AI client implementation (injected dependency)
            preparer: Content preparer for cleaning email bodies (injected dependency)
        """
        self._client = ai_client
        self._preparer = preparer

    def summarize(self, email: Email, include_action_items: bool = True) -> Dict[str, str]:
        """
        Generate a concise summary of an email.

        Args:
            email: Email object to summarize
            include_action_items: Whether to extract action items

        Returns:
            Dictionary with 'summary' and optionally 'action_items' keys
        """
        try:
            body = self._preparer.prepare(email.body, email.html_body, max_chars=8000)
            prompt = self._build_summarization_prompt(email, body, include_action_items)
            result_text = self._client.complete(prompt, max_tokens=1000)
            return self._parse_summary_response(result_text)

        except Exception as e:
            logger.error(f"Summarization failed for email {email.id}: {e}")
            return {
                'summary': f'Error generating summary: {str(e)}',
                'action_items': ''
            }

    def _build_summarization_prompt(self, email: Email, body: str, include_action_items: bool) -> str:
        """Build the summarization prompt.

        Pure function - testable without API calls.
        """
        action_items_instruction = ""
        if include_action_items:
            action_items_instruction = """
**3. Action Items:**
- List any tasks, requests, or actions required
- Use bullet points
- Write "None" if no actions needed"""

        return f"""Summarize this email concisely and identify any action items.

**Email Details:**
- **Subject:** {email.subject}
- **From:** {email.sender}
- **To:** {email.recipient}

**Email Content:**
{body}

**Instructions:**
Provide a structured summary with the following sections:

**1. Key Points:**
- Main topics and information (3-5 bullet points)
- Focus on the most important details

**2. Context:**
- One sentence about the purpose or context of this email
{action_items_instruction}

**Response Format:**
Summary: [concise summary paragraph]
Action Items: [bulleted list or "None"]

Respond now with your summary."""

    def _parse_summary_response(self, response_text: str) -> Dict[str, str]:
        """Parse AI summary response.

        Pure function - testable without API calls.
        """
        summary = ''
        action_items = ''

        if 'Summary:' in response_text and 'Action Items:' in response_text:
            parts = response_text.split('Action Items:', 1)
            summary = parts[0].replace('Summary:', '').strip()
            action_items = parts[1].strip()
        else:
            summary = response_text.strip()

        return {
            'summary': summary,
            'action_items': action_items
        }

    def summarize_thread(self, emails: list[Email]) -> str:
        """
        Summarize an entire email thread.

        Args:
            emails: List of emails in the thread (chronological order)

        Returns:
            Thread summary
        """
        try:
            if not emails:
                return "Empty thread"

            if len(emails) == 1:
                result = self.summarize(emails[0])
                return result['summary']

            thread_content = []
            for i, email in enumerate(emails):
                preview = self._preparer.prepare(email.body, email.html_body, max_chars=500)
                thread_content.append(
                    f"**Email {i+1}** (from {email.sender}, {email.received_date.strftime('%Y-%m-%d')}):\n{preview}"
                )

            thread_text = '\n\n'.join(thread_content)

            prompt = f"""Summarize this email thread, showing how the conversation evolved.

**Thread:**
{thread_text}

**Instructions:**
- Provide a brief overview of the conversation flow
- Highlight key decisions or outcomes
- Note any unresolved issues
- Keep it concise (3-5 sentences)

Respond with the thread summary now."""

            result = self._client.complete(prompt, max_tokens=800)
            return result if result else "Failed to summarize thread"

        except Exception as e:
            logger.error(f"Thread summarization failed: {e}")
            return f"Error summarizing thread: {str(e)}"

    def generate_response_suggestion(self, email: Email) -> str:
        """
        Generate a suggested response to an email.

        Args:
            email: Email to respond to

        Returns:
            Suggested response text
        """
        try:
            body = self._preparer.prepare(email.body, email.html_body, max_chars=3000)

            prompt = f"""Draft a professional response to this email.

**Original Email:**
- **Subject:** {email.subject}
- **From:** {email.sender}
- **Content:**
{body}

**Instructions:**
- Keep the tone professional and friendly
- Address all key points from the original email
- Keep it concise (3-5 sentences)
- Do not include greeting or signature (just the body)

Provide the suggested response now."""

            result = self._client.complete(prompt, max_tokens=600)
            return result if result else "Could not generate response"

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return f"Error generating response: {str(e)}"
