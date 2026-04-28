"""Natural language email search using Claude API."""

import logging
from typing import List, Dict, Any, Optional
from ai.client import AIClient

logger = logging.getLogger(__name__)

class EmailSearcher:
    """Natural language email search powered by AI.

    Separates business logic (query parsing, SQL building) from I/O (API calls).
    AI client is injected, making this class easy to test and provider-agnostic.
    """

    def __init__(self, ai_client: AIClient):
        """Initialize searcher with AI client.

        Args:
            ai_client: AI client implementation (injected dependency)
        """
        self._client = ai_client

    def parse_search_query(self, natural_query: str) -> Dict[str, Any]:
        """
        Convert natural language query to structured search parameters.

        Args:
            natural_query: User's search query in natural language

        Returns:
            Dictionary with search parameters (keywords, filters, date ranges)
        """
        try:
            prompt = self._build_query_parse_prompt(natural_query)
            result_text = self._client.complete(prompt, max_tokens=500)
            return self._parse_query_response(result_text, natural_query)

        except Exception as e:
            logger.error(f"Query parsing failed: {e}")
            # Fallback to simple keyword search
            return {
                'keywords': [natural_query],
                'sender': None,
                'date_range': None,
                'category': None,
                'status': None,
                'content_type': None
            }

    def _build_query_parse_prompt(self, natural_query: str) -> str:
        """Build prompt for parsing natural language query.

        Pure function - testable without API calls.

        Args:
            natural_query: User's search query

        Returns:
            Formatted prompt string
        """
        return f"""Convert this natural language search query into structured search parameters for an email database.

**User Query:** "{natural_query}"

**Instructions:**
Extract and structure the following information:

1. **Keywords**: Main search terms for subject/body/sender
2. **Sender Filter**: Specific sender(s) mentioned
3. **Date Filter**: Date range or relative time (e.g., "last week", "yesterday")
4. **Category Filter**: Email category (urgent, important, newsletter, receipts, social, can_wait)
5. **Status Filter**: Read/unread status
6. **Content Type**: Type of content (receipt, invoice, notification, etc.)

**Response Format (JSON-like):**
Keywords: [list of search terms]
Sender: [sender email or name, or "any"]
Date Range: [specific range or "any"]
Category: [category or "any"]
Status: [read/unread/any]
Content Type: [type or "any"]

Analyze the query and provide the structured parameters now."""

    def _parse_query_response(self, response_text: str, original_query: str) -> Dict[str, Any]:
        """Parse AI query analysis response.

        Pure function - testable without API calls.

        Args:
            response_text: Raw AI response
            original_query: Original user query (fallback)

        Returns:
            Structured search parameters
        """
        params = {
            'keywords': [],
            'sender': None,
            'date_range': None,
            'category': None,
            'status': None,
            'content_type': None
        }

        lines = response_text.strip().split('\n')

        for line in lines:
            line = line.strip()

            if line.lower().startswith('keywords:'):
                keywords_str = line.split(':', 1)[1].strip()
                # Extract keywords from various formats
                keywords = [
                    k.strip().strip('[]"\'')
                    for k in keywords_str.replace('[', '').replace(']', '').split(',')
                    if k.strip() and k.strip().lower() != 'any'
                ]
                params['keywords'] = keywords if keywords else [original_query]

            elif line.lower().startswith('sender:'):
                sender = line.split(':', 1)[1].strip().strip('"\'')
                if sender.lower() != 'any':
                    params['sender'] = sender

            elif line.lower().startswith('date range:'):
                date_range = line.split(':', 1)[1].strip().strip('"\'')
                if date_range.lower() != 'any':
                    params['date_range'] = date_range

            elif line.lower().startswith('category:'):
                category = line.split(':', 1)[1].strip().strip('"\'').lower()
                if category != 'any':
                    params['category'] = category

            elif line.lower().startswith('status:'):
                status = line.split(':', 1)[1].strip().strip('"\'').lower()
                if status in ['read', 'unread']:
                    params['status'] = status

            elif line.lower().startswith('content type:'):
                content_type = line.split(':', 1)[1].strip().strip('"\'')
                if content_type.lower() != 'any':
                    params['content_type'] = content_type

        return params

    def build_sql_query(self, search_params: Dict[str, Any]) -> tuple[str, List[Any]]:
        """
        Build SQL query from structured search parameters.

        Args:
            search_params: Structured search parameters

        Returns:
            Tuple of (SQL query string, parameter values)
        """
        conditions = []
        params = []

        # Keywords search (full-text)
        if search_params.get('keywords'):
            keywords = ' OR '.join(search_params['keywords'])
            conditions.append("""
                emails.rowid IN (
                    SELECT rowid FROM emails_fts WHERE emails_fts MATCH ?
                )
            """)
            params.append(keywords)

        # Sender filter
        if search_params.get('sender'):
            conditions.append("sender LIKE ?")
            params.append(f"%{search_params['sender']}%")

        # Category filter
        if search_params.get('category'):
            conditions.append("category = ?")
            params.append(search_params['category'])

        # Status filter
        if search_params.get('status'):
            is_read = 1 if search_params['status'] == 'read' else 0
            conditions.append("is_read = ?")
            params.append(is_read)

        # Date range (simplified - would need more sophisticated parsing)
        if search_params.get('date_range'):
            date_range = search_params['date_range'].lower()

            if 'today' in date_range:
                conditions.append("DATE(received_date) = DATE('now')")
            elif 'yesterday' in date_range:
                conditions.append("DATE(received_date) = DATE('now', '-1 day')")
            elif 'this week' in date_range or 'last 7 days' in date_range:
                conditions.append("received_date >= DATE('now', '-7 days')")
            elif 'this month' in date_range or 'last 30 days' in date_range:
                conditions.append("received_date >= DATE('now', '-30 days')")

        # Build final query
        where_clause = ' AND '.join(conditions) if conditions else '1=1'

        query = f"""
            SELECT * FROM emails
            WHERE {where_clause}
            ORDER BY received_date DESC
            LIMIT 50
        """

        return query, params

    def rank_results(self, results: List[Dict[str, Any]], original_query: str) -> List[Dict[str, Any]]:
        """
        Use AI to rank search results by relevance.

        Args:
            results: List of email search results
            original_query: Original search query

        Returns:
            Ranked list of results
        """
        if len(results) <= 1:
            return results

        try:
            # Prepare email summaries for ranking
            email_summaries = []
            for i, email in enumerate(results[:20]):  # Limit to top 20 for efficiency
                summary = f"{i}. Subject: {email['subject']}, From: {email['sender']}"
                email_summaries.append(summary)

            summaries_text = '\n'.join(email_summaries)

            prompt = f"""Rank these email search results by relevance to the user's query.

**User Query:** "{original_query}"

**Search Results:**
{summaries_text}

**Instructions:**
- Rank the emails by relevance to the query (most relevant first)
- Return the ranking as a comma-separated list of numbers (e.g., "3,7,1,5,...")
- Only include the top 10 most relevant results

**Response Format:**
Ranking: [comma-separated list of result numbers]

Provide the ranking now."""

            result_text = self._client.complete(prompt, max_tokens=300)

            # Parse ranking
            ranking = self._parse_ranking_response(result_text)

            # Reorder results
            if ranking:
                ranked_results = []
                for idx in ranking:
                    if 0 <= idx < len(results):
                        ranked_results.append(results[idx])

                # Add any remaining results not in ranking
                for i, email in enumerate(results):
                    if i not in ranking:
                        ranked_results.append(email)

                return ranked_results

            return results

        except Exception as e:
            logger.error(f"Ranking failed: {e}")
            return results

    def _parse_ranking_response(self, response_text: str) -> List[int]:
        """Parse ranking response from AI.

        Pure function - testable without API calls.

        Args:
            response_text: Raw AI response

        Returns:
            List of result indices in ranked order
        """
        ranking = []

        for line in response_text.strip().split('\n'):
            if line.lower().startswith('ranking:'):
                ranking_str = line.split(':', 1)[1].strip()
                # Parse comma-separated numbers
                try:
                    ranking = [
                        int(num.strip()) for num in ranking_str.split(',')
                        if num.strip().isdigit()
                    ]
                except ValueError:
                    pass
                break

        return ranking
