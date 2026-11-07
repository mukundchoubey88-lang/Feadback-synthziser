"""Google Gemini AI Provider Implementation.

Direct REST integration with Gemini v1beta generateContent API using httpx,
with provider-specific error classification distinguishing quota exhaustion
from transient rate limiting.
"""

import logging
import time
from typing import Any, Dict, Optional
import httpx

from app.core.config import settings
from app.integrations.ai.base import BaseAIProvider, parse_retry_after
from app.integrations.ai.exceptions import (
    AIProviderAuthError,
    AIProviderError,
    AIProviderInvalidRequestError,
    AIProviderQuotaExhaustedError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from app.integrations.ai.schemas import AIRequest, AIResponse, AIUsage

logger = logging.getLogger("ai_provider.gemini")


class GeminiProvider(BaseAIProvider):
    """Google Gemini integration using REST v1beta."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(
            name="gemini",
            default_model=model or settings.GEMINI_MODEL or "gemini-2.0-flash",
            timeout_seconds=timeout_seconds or settings.AI_REQUEST_TIMEOUT,
        )
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self._client = client

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def map_http_error(self, e: httpx.HTTPStatusError) -> AIProviderError:
        """Provider-specific mapping of Gemini HTTP error payloads.

        Interprets Google RPC status, error details, and reason codes together
        with HTTP status codes to accurately distinguish daily quota exhaustion
        from temporary rate limits and invalid credentials.
        """
        status = e.response.status_code
        retry_after = parse_retry_after(e.response)

        try:
            body = e.response.json()
            error_obj = body.get("error", {})
            err_msg = str(error_obj.get("message") or body)
            rpc_status = str(error_obj.get("status") or "")
            details = error_obj.get("details", [])
        except Exception:
            err_msg = e.response.text[:200]
            rpc_status = ""
            details = []

        lower_msg = err_msg.lower()

        # Extract reasons, metadata, and violation descriptions from Google RPC details
        reasons = []
        quota_limits = []
        descriptions = []
        if isinstance(details, list):
            for d in details:
                if isinstance(d, dict):
                    if "reason" in d:
                        reasons.append(str(d["reason"]).upper())
                    metadata = d.get("metadata", {})
                    if isinstance(metadata, dict) and "quota_limit" in metadata:
                        quota_limits.append(str(metadata["quota_limit"]).lower())
                    violations = d.get("violations", [])
                    if isinstance(violations, list):
                        for v in violations:
                            if isinstance(v, dict) and "description" in v:
                                descriptions.append(str(v["description"]).lower())

        quota_limits_str = " ".join(quota_limits)
        descriptions_str = " ".join(descriptions)

        # 429 RESOURCE_EXHAUSTED: Distinguish Quota Exhaustion vs Transient Rate Limit
        if status == 429 or rpc_status == "RESOURCE_EXHAUSTED":
            is_quota_exhausted = (
                "QUOTA_EXCEEDED" in reasons
                or "perday" in quota_limits_str
                or "daily" in quota_limits_str
                or "day" in quota_limits_str
                or "daily" in lower_msg
                or "daily" in descriptions_str
                or "free tier" in lower_msg
                or "billing" in lower_msg
                or "spend" in lower_msg
                or ("quota limit" in lower_msg and not ("minute" in lower_msg or "second" in lower_msg))
                or ("quota exceeded" in lower_msg and not ("minute" in lower_msg or "second" in lower_msg))
            )
            if is_quota_exhausted:
                return AIProviderQuotaExhaustedError(
                    message=f"Gemini quota/billing exhausted: {err_msg}",
                    provider=self.name,
                    status_code=status,
                    retry_after=retry_after,
                )

            # Otherwise, rate limit is transient (e.g., RequestsPerMinute, TPM, or temporary surge)
            return AIProviderRateLimitError(
                message=f"Gemini rate limit: {err_msg}",
                provider=self.name,
                status_code=status,
                retry_after=retry_after,
            )

        # 403 PERMISSION_DENIED: Auth error vs project suspended vs conservative fallback
        if status == 403 or rpc_status == "PERMISSION_DENIED":
            is_billing_suspended = (
                "CONSUMER_SUSPENDED" in reasons
                or "billing" in lower_msg
                or "disabled" in lower_msg
            )
            if is_billing_suspended:
                return AIProviderQuotaExhaustedError(
                    message=f"Gemini project/billing suspended: {err_msg}",
                    provider=self.name,
                    status_code=status,
                )

            # Conservative safe classification: treat permission denied as AuthError
            # This disables the provider in the circuit breaker, prevents futile retries,
            # and triggers seamless failover to secondary provider.
            return AIProviderAuthError(
                message=f"Gemini authentication/permission denied: {err_msg}",
                provider=self.name,
                status_code=status,
            )

        # 400 INVALID_ARGUMENT: Check for API Key format errors vs request errors
        if status == 400 or rpc_status == "INVALID_ARGUMENT":
            if "api key" in lower_msg or "API_KEY_INVALID" in reasons:
                return AIProviderAuthError(
                    message=f"Gemini invalid API key: {err_msg}",
                    provider=self.name,
                    status_code=status,
                )
            return AIProviderInvalidRequestError(
                message=f"Gemini invalid request: {err_msg}",
                provider=self.name,
                status_code=status,
            )

        # 5xx Service Unavailable / Internal Server Error
        if status >= 500:
            return AIProviderUnavailableError(
                message=f"Gemini unavailable ({status}): {err_msg}",
                provider=self.name,
                status_code=status,
                retry_after=retry_after,
            )

        # Fallback for other status codes
        return AIProviderError(
            message=f"Gemini HTTP {status}: {err_msg}",
            provider=self.name,
            status_code=status,
            retry_after=retry_after,
        )

    def _prepare_payload(self, request: AIRequest) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": request.prompt}],
                }
            ]
        }

        if request.system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": request.system_instruction}]
            }

        generation_config: Dict[str, Any] = {
            "temperature": request.temperature,
        }
        if request.max_output_tokens:
            generation_config["maxOutputTokens"] = request.max_output_tokens

        if request.response_schema is not None:
            generation_config["responseMimeType"] = "application/json"
            json_schema = request.response_schema.model_json_schema()
            generation_config["responseSchema"] = json_schema

        payload["generationConfig"] = generation_config
        return payload

    async def generate(self, request: AIRequest) -> AIResponse:
        """Execute request against Gemini API."""
        if not self.is_configured:
            raise AIProviderAuthError(
                message="Gemini API key is not configured",
                provider=self.name,
                status_code=401,
            )

        model = self.default_model
        url = f"{self.BASE_URL}/models/{model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,  # Header avoids leaking key in query logs
        }
        payload = self._prepare_payload(request)

        start_time = time.perf_counter()
        if self._client is not None:
            try:
                response = await self._client.post(url, json=payload, headers=headers)
                response.raise_for_status()
            except httpx.TimeoutException as te:
                raise AIProviderTimeoutError(
                    message=f"Gemini request timed out after {self._timeout_seconds}s: {str(te)}",
                    provider=self.name,
                ) from te
            except httpx.HTTPStatusError as hse:
                raise self.map_http_error(hse) from hse
            except httpx.RequestError as re:
                raise AIProviderUnavailableError(
                    message=f"Gemini connection error: {str(re)}",
                    provider=self.name,
                ) from re
        else:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                try:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                except httpx.TimeoutException as te:
                    raise AIProviderTimeoutError(
                        message=f"Gemini request timed out after {self._timeout_seconds}s: {str(te)}",
                        provider=self.name,
                    ) from te
                except httpx.HTTPStatusError as hse:
                    raise self.map_http_error(hse) from hse
                except httpx.RequestError as re:
                    raise AIProviderUnavailableError(
                        message=f"Gemini connection error: {str(re)}",
                        provider=self.name,
                    ) from re

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        data = response.json()

        # Extract text from candidate
        candidates = data.get("candidates", [])
        if not candidates:
            raise AIProviderUnavailableError(
                message="Gemini returned no candidates in response",
                provider=self.name,
            )

        parts = candidates[0].get("content", {}).get("parts", [])
        raw_text = parts[0].get("text", "") if parts else ""

        # Extract token usage
        usage_meta = data.get("usageMetadata", {})
        usage = AIUsage(
            prompt_tokens=usage_meta.get("promptTokenCount", 0),
            completion_tokens=usage_meta.get("candidatesTokenCount", 0),
            total_tokens=usage_meta.get("totalTokenCount", 0),
        )

        parsed_json, structured = self.validate_and_parse_response(
            raw_text, request.response_schema
        )

        return AIResponse(
            content=raw_text,
            raw_json=parsed_json,
            structured_data=structured,
            provider=self.name,
            model=model,
            latency_ms=round(latency_ms, 2),
            usage=usage,
            correlation_id=request.correlation_id,
        )
