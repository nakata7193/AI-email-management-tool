"""Email summarization using Claude API."""

import logging
from typing import Dict, Optional
from anthropic import Anthropic

from providers.base import Email
from config import claude_config
from parsers.email_parser import EmailParser

logger = logging.getLogger(__name__)

class EmailSummarizer:
    """AI-powered email summarization using Claude."""

    def __init__(self):
        self.client = Anthropic(api_key=claude_config.api_key)
        self.parser = EmailParser()

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
            # Prepare email content
            body = email.body

            if not body and email.html_body:
                body = self.parser.html_to_text(email.html_body)

            # Extract main content
            main_content, _ = self.parser.extract_quoted_reply(body)

            # Truncate for AI
            truncated_body = self.parser.truncate_for_ai(main_content, max_chars=8000)

            # Build prompt
            prompt = self._build_summarization_prompt(email, truncated_body, include_action_items)

            # Call Claude API with streaming for long emails
            response = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=1000,
                thinking={
                    "type": "adaptive"
                },
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Get final response
            result_text = response.content[-1].text if response.content else ""

            return self._parse_summary_response(result_text)

        except Exception as e:
            logger.error(f"Summarization failed for email {email.id}: {e}")
            return {
                'summary': f'Error generating summary: {str(e)}',
                'action_items': ''
            }

    def _build_summarization_prompt(self, email: Email, body: str, include_action_items: bool) -> str:
        """Build the summarization prompt for Claude."""
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
        """Parse Claude's summary response."""
        summary = ''
        action_items = ''

        # Try to extract structured sections
        if 'Summary:' in response_text and 'Action Items:' in response_text:
            parts = response_text.split('Action Items:', 1)
            summary = parts[0].replace('Summary:', '').strip()
            action_items = parts[1].strip()
        else:
            # Fallback: use entire response as summary
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

            # Build thread context
            thread_content = []
            for i, email in enumerate(emails):
                body = email.body or self.parser.html_to_text(email.html_body or '')
                main_content, _ = self.parser.extract_quoted_reply(body)
                preview = self.parser.get_text_preview(main_content, length=500)

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

            response = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=800,
                thinking={
                    "type": "adaptive"
                },
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            return response.content[-1].text if response.content else "Failed to summarize thread"

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
            body = email.body or self.parser.html_to_text(email.html_body or '')
            main_content, _ = self.parser.extract_quoted_reply(body)

            prompt = f"""Draft a professional response to this email.

**Original Email:**
- **Subject:** {email.subject}
- **From:** {email.sender}
- **Content:**
{main_content[:3000]}

**Instructions:**
- Keep the tone professional and friendly
- Address all key points from the original email
- Keep it concise (3-5 sentences)
- Do not include greeting or signature (just the body)

Provide the suggested response now."""

            response = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=600,
                thinking={
                    "type": "adaptive"
                },
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            return response.content[-1].text if response.content else "Could not generate response"

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return f"Error generating response: {str(e)}"
