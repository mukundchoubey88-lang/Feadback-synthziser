"""AI Provider Exceptions.

Hierarchical exception types for multi-provider error handling,
automatic failover classification, and privacy-safe diagnostics.
"""

from typing import List, Optional, Tuple


class AIProviderError(Exception):
    """Base exception for all AI provider operations."""

    def __init__(
        self,
        message: str,
        provider: str,
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


class AIProviderRateLimitError(AIProviderError):
    """Raised when provider returns HTTP 429 Rate Limit Exceeded."""

    def __init__(
        self,
        message: str,
        provider: str,
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


class AIProviderQuotaExhaustedError(AIProviderError):
    """Raised when provider returns HTTP 402/403 or quota exhausted error."""

    def __init__(
        self,
        message: str,
        provider: str,
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


class AIProviderUnavailableError(AIProviderError):
    """Raised when provider returns HTTP 5xx or server is down."""

    def __init__(
        self,
        message: str,
        provider: str,
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


class AIProviderTimeoutError(AIProviderError):
    """Raised when request to provider times out."""

    def __init__(
        self,
        message: str,
        provider: str,
        retry_after: Optional[float] = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            status_code=408,
            retry_after=retry_after,
            is_transient=True,
        )


class AIProviderAuthError(AIProviderError):
    """Raised on authentication or invalid API key failure (401/403)."""

    def __init__(
        self,
        message: str,
        provider: str,
        status_code: Optional[int] = 401,
    ):
        super().__init__(
            message=message,
            provider=provider,
            status_code=status_code,
            retry_after=None,
            is_transient=False,
        )


class AIProviderInvalidRequestError(AIProviderError):
    """Raised when client sends a malformed or invalid request (HTTP 400).

    This indicates a bug or invalid payload from the caller and MUST NOT
    be retried or trigger automatic provider failover.
    """

    def __init__(
        self,
        message: str,
        provider: str,
        status_code: Optional[int] = 400,
    ):
        super().__init__(
            message=message,
            provider=provider,
            status_code=status_code,
            retry_after=None,
            is_transient=False,
        )


class AIProviderValidationError(AIProviderError):
    """Raised when provider response does not conform to expected schema."""

    def __init__(
        self,
        message: str,
        provider: str,
        raw_output: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            status_code=None,
            retry_after=None,
            is_transient=True,  # May succeed on 1 repair retry or fallback provider
        )
        self.raw_output = raw_output


class AllAIProvidersFailedError(Exception):
    """Raised when all configured AI providers fail in sequence."""

    def __init__(
        self,
        message: str,
        failures: List[Tuple[str, Exception]],
    ):
        super().__init__(message)
        self.message = message
        self.failures = failures

    def __str__(self) -> str:
        details = ", ".join(f"{prov}: {type(err).__name__} ({err})" for prov, err in self.failures)
        return f"{self.message} -> [{details}]"
