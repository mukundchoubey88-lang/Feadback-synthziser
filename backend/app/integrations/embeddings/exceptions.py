"""Typed exceptions for embedding services.

Provides structured, hierarchical exceptions distinguishing configuration,
authentication, rate limits, quota exhaustion, network/server errors,
and response validation failures.
"""

from typing import Optional


class EmbeddingError(Exception):
    """Base exception for all embedding operations."""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        status_code: Optional[int] = None,
        retry_after: Optional[float] = None,
        is_transient: bool = False,
    ):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code
        self.retry_after = retry_after
        self.is_transient = is_transient

    def __str__(self) -> str:
        parts = [f"[{self.provider}] {self.message}"]
        if self.status_code is not None:
            parts.append(f"(status: {self.status_code})")
        if self.retry_after is not None:
            parts.append(f"(retry_after: {self.retry_after}s)")
        return " ".join(parts)


class EmbeddingConfigurationError(EmbeddingError):
    """Raised when an embedding provider is not configured properly (e.g. missing API key)."""

    def __init__(self, message: str, provider: str = "unknown"):
        super().__init__(
            message=message,
            provider=provider,
            status_code=None,
            retry_after=None,
            is_transient=False,
        )


class EmbeddingAuthError(EmbeddingError):
    """Raised on authentication or authorization failure (HTTP 401/403 or invalid key)."""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        status_code: Optional[int] = 401,
    ):
        super().__init__(
            message=message,
            provider=provider,
            status_code=status_code,
            retry_after=None,
            is_transient=False,
        )


class EmbeddingRateLimitError(EmbeddingError):
    """Raised when rate limits are exceeded (HTTP 429)."""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        status_code: Optional[int] = 429,
        retry_after: Optional[float] = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            status_code=status_code,
            retry_after=retry_after,
            is_transient=True,
        )


class EmbeddingQuotaExhaustedError(EmbeddingError):
    """Raised when hard quota or billing credit is exhausted."""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        status_code: Optional[int] = None,
        retry_after: Optional[float] = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            status_code=status_code,
            retry_after=retry_after,
            is_transient=False,
        )


class EmbeddingUnavailableError(EmbeddingError):
    """Raised when server returns 5xx or connection fails."""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        status_code: Optional[int] = 503,
        retry_after: Optional[float] = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            status_code=status_code,
            retry_after=retry_after,
            is_transient=True,
        )


class EmbeddingTimeoutError(EmbeddingError):
    """Raised when an embedding request times out."""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        status_code: Optional[int] = 408,
        retry_after: Optional[float] = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            status_code=status_code,
            retry_after=retry_after,
            is_transient=True,
        )


class EmbeddingInvalidRequestError(EmbeddingError):
    """Raised when input text is invalid, empty, or HTTP 400 is returned."""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        status_code: Optional[int] = 400,
    ):
        super().__init__(
            message=message,
            provider=provider,
            status_code=status_code,
            retry_after=None,
            is_transient=False,
        )


class EmbeddingValidationError(EmbeddingError):
    """Raised when the provider response format, dimension, or values (e.g. NaN) are invalid."""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        status_code: Optional[int] = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            status_code=status_code,
            retry_after=None,
            is_transient=False,
        )
