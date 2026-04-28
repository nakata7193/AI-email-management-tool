"""Service layer for business logic."""

from .email_service import EmailService, FetchResult, CategorizeResult, SearchResult

__all__ = ['EmailService', 'FetchResult', 'CategorizeResult', 'SearchResult']
