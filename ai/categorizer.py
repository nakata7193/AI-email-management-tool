"""Email categorization using Claude API."""

import logging
from typing import Dict, Optional
from ai.client import AIClient
from providers.base import Email
from parsers.email_parser import EmailParser

logger = logging.getLogger(__name__)

class EmailCategorizer:
    """AI-powered email categorization.

    Separates business logic (prompt building, parsing) from I/O (API calls).
    AI client is injected, making this class easy to test and provider-agnostic.
    """

    CATEGORIES = {
        'urgent': 'Requires immediate action or response',
        'important': 'Needs attention soon but not urgent',
        'newsletter': 'Bulk, marketing, or subscription content',
        'receipts': 'Purchase confirmations, invoices, orders',
        'social': 'Social media notifications and updates',
        'can_wait': 'Low priority, can be addressed later'
    }

    def __init__(self, ai_client: AIClient):
        """Initialize categorizer with AI client.

        Args:
            ai_client: AI client implementation (injected dependency)
        """
        self._client = ai_client
        self._parser = EmailParser()

    def categorize(self, email: Email) -> Dict[str, str]:
        """
        Categorize an email using AI.

        Args:
            email: Email object to categorize

        Returns:
            Dictionary with 'category' and 'reasoning' keys
        """
        try:
            # Prepare email content
            body = self._prepare_body(email)

            # Build categorization prompt
            prompt = self._build_categorization_prompt(email, body)

            # Call AI (injected dependency handles I/O)
            result_text = self._client.complete(prompt, max_tokens=500)

            # Parse response
            return self._parse_categorization_response(result_text)

        except Exception as e:
            logger.error(f"Categorization failed for email {email.id}: {e}")
            return {
                'category': 'can_wait',
                'reasoning': f'Error during categorization: {str(e)}'
            }

    def _prepare_body(self, email: Email) -> str:
        """Prepare email body for AI processing.

        Pure function - testable without API calls.

        Args:
            email: Email object

        Returns:
            Cleaned and truncated email body
        """
        # Convert HTML to text if needed
        body = email.body
        if not body and email.html_body:
            body = self._parser.html_to_text(email.html_body)

        # Extract main content (remove quoted replies)
        main_content, _ = self._parser.extract_quoted_reply(body)

        # Truncate for AI processing
        return self._parser.truncate_for_ai(main_content, max_chars=5000)

    def _build_categorization_prompt(self, email: Email, body: str) -> str:
        """Build the categorization prompt.

        Pure function - testable without API calls.

        Args:
            email: Email object
            body: Prepared email body

        Returns:
            Formatted prompt string
        """
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
        """Parse AI categorization response.

        Pure function - testable without API calls.

        Args:
            response_text: Raw AI response

        Returns:
            Dictionary with 'category' and 'reasoning' keys
        """
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
