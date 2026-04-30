"""Email categorization using Claude API."""

import re
import logging
from typing import Dict, List, Optional
from ai.client import AIClient
from providers.base import Email
from parsers.email_parser import ContentPreparer

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


class EmailCategorizer:
    """AI-powered email categorization.

    Separates business logic (prompt building, parsing) from I/O (API calls).
    AI client, content preparer, and categories are all injected, making this
    class fully testable without filesystem access.
    """

    def __init__(self, ai_client: AIClient, preparer: ContentPreparer, categories: Dict[str, str]):
        """Initialize categorizer with AI client, content preparer, and categories.

        Args:
            ai_client: AI client implementation (injected dependency)
            preparer: Content preparer for cleaning email bodies (injected dependency)
            categories: Mapping of category name -> description (injected dependency)
        """
        self._client = ai_client
        self._preparer = preparer
        self._categories = categories

    def categorize(self, email: Email) -> Dict[str, str]:
        """Categorize a single email using AI.

        Used for one-off operations (e.g. summarize context).
        For bulk categorization use batch_categorize() instead.

        Args:
            email: Email object to categorize

        Returns:
            Dictionary with 'category' and 'reasoning' keys
        """
        categories = self._categories

        try:
            body = self._preparer.prepare(email.body, email.html_body, max_chars=5000)
            prompt = self._build_single_prompt(email, body, categories)
            result_text = self._client.complete(prompt, max_tokens=200)
            return self._parse_single_response(result_text, categories)

        except Exception as e:
            logger.error(f"Categorization failed for email {email.id}: {e}")
            fallback = next(iter(categories), 'other')
            return {
                'category': fallback,
                'reasoning': f'Error during categorization: {str(e)}'
            }

    def batch_categorize(self, emails: List[Email]) -> Dict[str, Dict[str, str]]:
        """Categorize multiple emails in batches of 100 per API call.

        Sends up to BATCH_SIZE emails in a single compact prompt, getting back
        one category per line. Much cheaper and faster than one call per email.

        Args:
            emails: List of Email objects to categorize

        Returns:
            Dict mapping email ID -> {'category': str, 'reasoning': str}
        """
        categories = self._categories
        results: Dict[str, Dict[str, str]] = {}
        fallback = next(iter(categories), 'other')

        for batch_start in range(0, len(emails), BATCH_SIZE):
            batch = emails[batch_start:batch_start + BATCH_SIZE]

            try:
                prompt = self._build_batch_prompt(batch, categories)
                max_tokens = len(batch) * 20  # ~20 tokens per output line
                response_text = self._client.complete(prompt, max_tokens=max_tokens)
                batch_results = self._parse_batch_response(response_text, batch, categories)
                results.update(batch_results)

            except Exception as e:
                logger.error(f"Batch categorization failed for batch starting at {batch_start}: {e}")
                for email in batch:
                    results[email.id] = {
                        'category': fallback,
                        'reasoning': f'Batch categorization error: {str(e)}'
                    }

        return results

    def _build_single_prompt(self, email: Email, body: str, categories: Dict[str, str]) -> str:
        """Build prompt for single-email categorization."""
        categories_desc = '\n'.join(
            f"- **{cat}**: {desc}" for cat, desc in categories.items()
        )

        return f"""Analyze this email and categorize it into one of the predefined categories.

**Email Details:**
- **Subject:** {email.subject}
- **From:** {email.sender}
- **Body:**
{body}

**Available Categories:**
{categories_desc}

**Response Format:**
Category: [category_name]
Reasoning: [your reasoning in 1-2 sentences]"""

    def _build_batch_prompt(self, emails: List[Email], categories: Dict[str, str]) -> str:
        """Build compact batch prompt for multiple emails in one API call."""
        email_summaries = []
        for i, email in enumerate(emails, 1):
            body = self._preparer.prepare(email.body, email.html_body, max_chars=400)
            email_summaries.append(
                f"{i}. Subject: {email.subject}\n"
                f"   From: {email.sender}\n"
                f"   Body: {body}"
            )

        category_names = ', '.join(categories.keys())

        return f"""Categorize these {len(emails)} emails.

{chr(10).join(email_summaries)}

Categories (use ONLY these, use "other" if unsure): {category_names}

Response: one line per email
<number>. <category>

Example:
1. newsletter
2. receipt
3. other"""

    def _parse_single_response(self, response_text: str, categories: Dict[str, str]) -> Dict[str, str]:
        """Parse single-email categorization response."""
        fallback = next(iter(categories), 'other')
        category = fallback
        reasoning = ''

        for line in response_text.strip().split('\n'):
            line = line.strip()
            if line.lower().startswith('category:'):
                cat = line.split(':', 1)[1].strip().lower()
                if cat in categories:
                    category = cat
            elif line.lower().startswith('reasoning:'):
                reasoning = line.split(':', 1)[1].strip()

        return {
            'category': category,
            'reasoning': reasoning or 'No reasoning provided'
        }

    def _parse_batch_response(
        self,
        response_text: str,
        emails: List[Email],
        categories: Dict[str, str]
    ) -> Dict[str, Dict[str, str]]:
        """Parse batch categorization response.

        Maps `N. category` lines back to email IDs by position.
        Falls back to last category if a line is missing or unrecognised.
        """
        fallback = next(iter(categories), 'other')
        position_map: Dict[int, str] = {}

        for line in response_text.strip().split('\n'):
            line = line.strip()
            match = re.match(r'^(\d+)\.\s+(\S+)', line)
            if match:
                pos = int(match.group(1))
                cat = match.group(2).lower().rstrip('.,;')
                position_map[pos] = cat if cat in categories else fallback

        results: Dict[str, Dict[str, str]] = {}
        for i, email in enumerate(emails, 1):
            category = position_map.get(i, fallback)
            results[email.id] = {
                'category': category,
                'reasoning': 'Batch categorized'
            }

        return results
