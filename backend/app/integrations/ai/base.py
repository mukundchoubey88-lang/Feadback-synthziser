"""Base AI Provider Interface.

Defines the abstract base class and common utilities for all AI providers.
"""

from abc import ABC, abstractmethod
import datetime
from email.utils import parsedate_to_datetime
import json
import logging
from typing import Any, Dict, Optional, Tuple, Type
import httpx
from pydantic import BaseModel, ValidationError

from app.integrations.ai.schemas import AIRequest, AIResponse
from app.integrations.ai.exceptions import (
    AIProviderAuthError,
    AIProviderError,
    AIProviderInvalidRequestError,
    AIProviderQuotaExhaustedError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    AIProviderValidationError,
)

logger = logging.getLogger("ai_provider")


def parse_retry_after(response: Optional[httpx.Response]) -> Optional[float]:
    """Extract and parse 'Retry-After' header in seconds if present."""
    if response is None:
        return None
    val = response.headers.get("Retry-After") or response.headers.get("retry-after")
    if not val:
        return None
    try:
        # Check if it's integer/float seconds
        return float(val)
    except ValueError:
        pass
    try:
        # Check if it's an HTTP date
        dt = parsedate_to_datetime(val)
        delta = (dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
        return max(0.0, delta)
    except Exception:
        return None


class BaseAIProvider(ABC):
    """Abstract Base Class for an AI completion provider."""

    def __init__(self, name: str, default_model: str, timeout_seconds: float = 30.0):
        self._name = name.lower()
        self._default_model = default_model
        self._timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        """The canonical lower-case name of the provider."""
        return self._name

    @property
    def default_model(self) -> str:
        """Default model identifier for this provider."""
        return self._default_model

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if required API credentials and settings are present."""
        pass

    @abstractmethod
    async def generate(self, request: AIRequest) -> AIResponse:
        """Execute a generation request against the provider."""
        pass

    def validate_and_parse_response(
        self,
        raw_text: str,
        schema: Optional[Type[BaseModel]],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[BaseModel]]:
        """Safely parse JSON and validate against schema if requested."""
        if not schema and not raw_text.strip().startswith(("{", "[")):
            return None, None

        # Clean markdown code blocks if the model wrapped output in ```json ... ```
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            parsed_json = json.loads(cleaned)
        except Exception as e:
            if schema:
                raise AIProviderValidationError(
                    message=f"Failed to parse JSON response: {str(e)}",
                    provider=self.name,
                    raw_output=raw_text[:500],
                ) from e
            return None, None

        if schema:
            try:
                validated = schema.model_validate(parsed_json)
                return parsed_json, validated
            except ValidationError as ve:
                raise AIProviderValidationError(
                    message=f"Response does not match expected schema: {str(ve)}",
                    provider=self.name,
                    raw_output=cleaned[:500],
                ) from ve

        return parsed_json, None

    def map_http_error(self, e: httpx.HTTPStatusError) -> AIProviderError:
        """Map HTTP error status codes to classified AIProviderError hierarchy."""
        status = e.response.status_code
        retry_after = parse_retry_after(e.response)

        try:
            body = e.response.json()
            err_msg = str(body.get("error", {}).get("message") or body)
        except Exception:
            err_msg = e.response.text[:200]

        # Fallback error mapping for generic / unknown provider error payloads
        lower_msg = err_msg.lower()

        # 402 Payment Required or explicitly exhausted quota/credits
        if status == 402 or (status in (429, 403) and ("quota exhausted" in lower_msg or "insufficient credits" in lower_msg or "billing" in lower_msg)):
            return AIProviderQuotaExhaustedError(
                message=f"Quota exhausted: {err_msg}",
                provider=self.name,
                status_code=status,
                retry_after=retry_after,
            )

        if status == 429:
            return AIProviderRateLimitError(
                message=f"Rate limited: {err_msg}",
                provider=self.name,
                status_code=status,
                retry_after=retry_after,
            )

        if status in (401, 403):
            # Conservative safe classification: treat 401/403 as AuthError to prevent futile retries
            return AIProviderAuthError(
                message=f"Authentication/Authorization error: {err_msg}",
                provider=self.name,
                status_code=status,
            )

        if status == 400:
            return AIProviderInvalidRequestError(
                message=f"Invalid request (400): {err_msg}",
                provider=self.name,
                status_code=status,
            )

        if status >= 500:
            return AIProviderUnavailableError(
                message=f"Provider unavailable ({status}): {err_msg}",
                provider=self.name,
                status_code=status,
                retry_after=retry_after,
            )

        return AIProviderError(
            message=f"HTTP {status} error: {err_msg}",
            provider=self.name,
            status_code=status,
            retry_after=retry_after,
            is_transient=False,
        )
