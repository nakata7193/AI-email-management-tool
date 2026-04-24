"""Email categorization using Claude API."""

import logging
from typing import Dict, Optional
from anthropic import Anthropic

from providers.base import Email
from config import claude_config
from parsers.email_parser import EmailParser

logger = logging.getLogger(__name__)

class EmailCategorizer:
    """AI-powered email categorization using Claude."""

    CATEGORIES = {
        'urgent': 'Requires immediate action or response',
        'important': 'Needs attention soon but not urgent',
        'newsletter': 'Bulk, marketing, or subscription content',
        'receipts': 'Purchase confirmations, invoices, orders',
        'social': 'Social media notifications and updates',
        'can_wait': 'Low priority, can be addressed later'
    }

    def __init__(self):
        self.client = Anthropic(api_key=claude_config.api_key)
        self.parser = EmailParser()

    def categorize(self, email: Email) -> Dict[str, str]:
        """
        Categorize an email using Claude API.

        Args:
            email: Email object to categorize

        Returns:
            Dictionary with 'category' and 'reasoning' keys
        """
        try:
            # Prepare email content for Claude
            body = email.body

            # Convert HTML to text if needed
            if not body and email.html_body:
                body = self.parser.html_to_text(email.html_body)

            # Extract main content (remove quoted replies)
            main_content, _ = self.parser.extract_quoted_reply(body)

            # Truncate for AI processing
            truncated_body = self.parser.truncate_for_ai(main_content, max_chars=5000)

            # Build categorization prompt
            prompt = self._build_categorization_prompt(email, truncated_body)

            # Call Claude API with adaptive thinking
            response = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=500,
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

            # Parse response
            result_text = response.content[-1].text if response.content else ""

            return self._parse_categorization_response(result_text)

        except Exception as e:
            logger.error(f"Categorization failed for email {email.id}: {e}")
            return {
                'category': 'can_wait',
                'reasoning': f'Error during categorization: {str(e)}'
            }

    def _build_categorization_prompt(self, email: Email, body: str) -> str:
        """Build the categorization prompt for Claude."""
        categories_desc = '\n'.join([
            f"- **{cat}**: {desc}"
            for cat, desc in self.CATEGORIES.items()
        ])

        return f"""Analyze this email and categorize it into one of the predefined categories.

**Email Details:**
- **Subject:** {email.subject}
- **From:** {email.sender}
- **To:** {email.recipient}
- **Body:**
{body}

**Available Categories:**
{categories_desc}

**Instructions:**
1. Choose the MOST appropriate category from the list above
2. Provide clear reasoning for your choice
3. Consider urgency, sender importance, and content type

**Response Format:**
Category: [category_name]
Reasoning: [your reasoning in 1-2 sentences]

Respond now with your categorization."""

    def _parse_categorization_response(self, response_text: str) -> Dict[str, str]:
        """Parse Claude's categorization response."""
        category = 'can_wait'  # Default
        reasoning = ''

        lines = response_text.strip().split('\n')

        for line in lines:
            line = line.strip()

            if line.lower().startswith('category:'):
                cat = line.split(':', 1)[1].strip().lower()
                if cat in self.CATEGORIES:
                    category = cat

            elif line.lower().startswith('reasoning:'):
                reasoning = line.split(':', 1)[1].strip()

        return {
            'category': category,
            'reasoning': reasoning or 'No reasoning provided'
        }

    def batch_categorize(self, emails: list[Email], use_prompt_caching: bool = True) -> Dict[str, Dict[str, str]]:
        """
        Categorize multiple emails efficiently.

        Args:
            emails: List of emails to categorize
            use_prompt_caching: Enable prompt caching for efficiency

        Returns:
            Dictionary mapping email IDs to categorization results
        """
        results = {}

        for email in emails:
            try:
                result = self.categorize(email)
                results[email.id] = result

            except Exception as e:
                logger.error(f"Failed to categorize email {email.id}: {e}")
                results[email.id] = {
                    'category': 'can_wait',
                    'reasoning': f'Batch categorization error: {str(e)}'
                }

        logger.info(f"Categorized {len(results)} emails")
        return results
