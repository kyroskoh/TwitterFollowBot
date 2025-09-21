"""
Custom exceptions for X Follow Bot.
"""

from typing import Optional, Any, Dict


class XFollowBotError(Exception):
    """Base exception for X Follow Bot."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AuthenticationError(XFollowBotError):
    """Raised when authentication fails."""
    pass


class RateLimitError(XFollowBotError):
    """Raised when hitting API rate limits."""
    
    def __init__(
        self,
        message: str,
        reset_time: Optional[int] = None,
        limit: Optional[int] = None,
        remaining: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)
        self.reset_time = reset_time
        self.limit = limit
        self.remaining = remaining


class APIError(XFollowBotError):
    """Raised when X API returns an error."""
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)
        self.status_code = status_code
        self.error_code = error_code


class ConfigurationError(XFollowBotError):
    """Raised when configuration is invalid."""
    pass


class DatabaseError(XFollowBotError):
    """Raised when database operations fail."""
    pass


class ValidationError(XFollowBotError):
    """Raised when data validation fails."""
    pass