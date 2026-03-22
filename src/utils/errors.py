"""
Inzyts Error Hierarchy.

Defines the standard exception hierarchy for the application to ensure
consistent error handling, logging, and user feedback.
"""

from typing import Optional, Any, Dict


class InzytsError(Exception):
    """Base class for all application-specific exceptions."""

    # Default HTTP status code for this error family.
    # Subclasses override to provide more specific status codes.
    http_status: int = 500

    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.original_error = original_error
        self.details = details or {}

    def __str__(self):
        if self.original_error:
            return f"{self.message} (Caused by: {self.original_error})"
        return self.message


class DataLoadingError(InzytsError):
    """Raised when loading data fails (IO, parsing, encoding)."""

    http_status = 400


class DataValidationError(InzytsError, ValueError):
    """Raised when data fails validation checks (empty, types).

    Also inherits from ValueError so Pydantic field validators catch it
    and convert it to a 422 validation error automatically.
    """

    http_status = 422


class CacheError(InzytsError):
    """Raised when cache operations fail."""

    http_status = 500


class AnalysisError(InzytsError):
    """Raised when an analysis step fails."""

    http_status = 500


class LLMError(InzytsError):
    """Raised when LLM communication or parsing fails."""

    http_status = 502


class ConfigurationError(InzytsError):
    """Raised when configuration or environment is invalid."""

    http_status = 500


class PathTraversalError(InzytsError):
    """Raised when a path escapes allowed directories."""

    http_status = 403


def to_http_exception(exc: InzytsError) -> "HTTPException":
    """Convert an InzytsError into a FastAPI HTTPException.

    Import is deferred to avoid a hard dependency on FastAPI in non-server
    code that only uses the error classes.
    """
    from fastapi import HTTPException

    return HTTPException(status_code=exc.http_status, detail=exc.message)
