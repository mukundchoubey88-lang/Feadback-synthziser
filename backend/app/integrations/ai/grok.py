"""xAI Grok AI Provider Implementation.

Direct REST integration with xAI Responses API (https://api.x.ai/v1/responses)
supporting JSON schema structured outputs, provider-specific error mapping,
and token usage metrics.
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

logger = logging.getLogger("ai_provider.grok")


class GrokProvider(BaseAIProvider):
    """xAI Grok integration using the official Responses API."""

    API_URL = "https://api.x.ai/v1/responses"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(
            name="grok",
            default_model=model or settings.XAI_MODEL or "grok-4.7",
            timeout_seconds=timeout_seconds or settings.AI_REQUEST_TIMEOUT,
        )
        self.api_key = api_key if api_key is not None else settings.XAI_API_KEY
        self._client = client

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def map_http_error(self, e: httpx.HTTPStatusError) -> AIProviderError:
        """Provider-specific mapping of xAI Grok error payloads.

        Interprets xAI error object (type, code, message) to distinguish
        authentication failures and quota exhaustion from temporary rate limits.
        """
        status = e.response.status_code
        retry_after = parse_retry_after(e.response)

        try:
            body = e.response.json()
            error_obj = body.get("error", {})
            err_msg = str(error_obj.get("message") or body)
            err_type = str(error_obj.get("type") or "")
            err_code = str(error_obj.get("code") or "")
        except Exception:
            err_msg = e.response.text[:200]
            err_type = ""
            err_code = ""

        lower_msg = err_msg.lower()

        # 401 Authentication Error
        if (
            status == 401
            or err_code == "invalid_api_key"
            or err_type == "authentication_error"
            or "api key" in lower_msg
        ):
            return AIProviderAuthError(
                message=f"xAI Grok authentication failed: {err_msg}",
                provider=self.name,
                status_code=status,
            )

        # 402 or Quota / Credit exhaustion
        is_quota = (
            status == 402
            or err_type == "insufficient_quota"
            or err_code == "insufficient_quota"
            or "quota" in lower_msg
            or "credit" in lower_msg
            or "billing" in lower_msg
        )
        if is_quota:
            return AIProviderQuotaExhaustedError(
                message=f"xAI Grok quota exhausted: {err_msg}",
                provider=self.name,
                status_code=status,
                retry_after=retry_after,
            )

        # 403 Forbidden
        if status == 403:
            if "quota" in lower_msg or "credit" in lower_msg or "billing" in lower_msg:
                return AIProviderQuotaExhaustedError(
                    message=f"xAI Grok account/billing suspended: {err_msg}",
                    provider=self.name,
                    status_code=status,
                )
            return AIProviderAuthError(
                message=f"xAI Grok authorization forbidden: {err_msg}",
                provider=self.name,
                status_code=status,
            )

        # 429 Rate Limit
        if status == 429 or err_type == "rate_limit_error":
            return AIProviderRateLimitError(
                message=f"xAI Grok rate limit: {err_msg}",
                provider=self.name,
                status_code=status,
                retry_after=retry_after,
            )

        # 400 Invalid Request
        if status == 400 or err_type == "invalid_request_error":
            return AIProviderInvalidRequestError(
                message=f"xAI Grok invalid request: {err_msg}",
                provider=self.name,
                status_code=status,
            )

        # 5xx
        if status >= 500:
            return AIProviderUnavailableError(
                message=f"xAI Grok unavailable ({status}): {err_msg}",
                provider=self.name,
                status_code=status,
                retry_after=retry_after,
            )

        return AIProviderError(
            message=f"xAI Grok HTTP {status}: {err_msg}",
            provider=self.name,
            status_code=status,
            retry_after=retry_after,
        )

    def _prepare_payload(self, request: AIRequest) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.default_model,
            "input": [
                {
                    "role": "user",
                    "content": request.prompt,
                }
            ],
            "temperature": request.temperature,
        }

        if request.system_instruction:
            payload["instructions"] = request.system_instruction

        if request.max_output_tokens:
            payload["max_output_tokens"] = request.max_output_tokens

        # Use Responses API text.format configuration
        if request.response_schema is not None:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": request.response_schema.__name__,
                    "schema": request.response_schema.model_json_schema(),
                }
            }

        return payload

    def _extract_text_content(self, data: Dict[str, Any]) -> str:
        """Extract completion text from xAI Responses API payload."""
        if "output_text" in data and isinstance(data["output_text"], str):
            return data["output_text"]

        output = data.get("output")
        if isinstance(output, list):
            for item in output:
                if isinstance(item, dict):
                    content = item.get("content")
                    if isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and "text" in part:
                                return part["text"]
                            if isinstance(part, str):
                                return part
                    elif isinstance(content, str):
                        return content
                elif isinstance(item, str):
                    return item

        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message", {})
            return msg.get("content", "")

        return ""

    async def generate(self, request: AIRequest) -> AIResponse:
        """Execute request against xAI Responses API."""
        if not self.is_configured:
            raise AIProviderAuthError(
                message="xAI API key is not configured",
                provider=self.name,
                status_code=401,
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._prepare_payload(request)

        start_time = time.perf_counter()
        if self._client is not None:
            try:
                response = await self._client.post(
                    self.API_URL, json=payload, headers=headers
                )
                response.raise_for_status()
            except httpx.TimeoutException as te:
                raise AIProviderTimeoutError(
                    message=f"Grok request timed out after {self._timeout_seconds}s: {str(te)}",
                    provider=self.name,
                ) from te
            except httpx.HTTPStatusError as hse:
                raise self.map_http_error(hse) from hse
            except httpx.RequestError as re:
                raise AIProviderUnavailableError(
                    message=f"Grok connection error: {str(re)}",
                    provider=self.name,
                ) from re
        else:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                try:
                    response = await client.post(
                        self.API_URL, json=payload, headers=headers
                    )
                    response.raise_for_status()
                except httpx.TimeoutException as te:
                    raise AIProviderTimeoutError(
                        message=f"Grok request timed out after {self._timeout_seconds}s: {str(te)}",
                        provider=self.name,
                    ) from te
                except httpx.HTTPStatusError as hse:
                    raise self.map_http_error(hse) from hse
                except httpx.RequestError as re:
                    raise AIProviderUnavailableError(
                        message=f"Grok connection error: {str(re)}",
                        provider=self.name,
                    ) from re

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        data = response.json()

        raw_text = self._extract_text_content(data)
        if not raw_text and not request.response_schema:
            logger.warning("Grok response did not contain text content")

        model = data.get("model", self.default_model)

        # Extract usage
        usage_meta = data.get("usage", {})
        prompt_tokens = usage_meta.get("input_tokens") or usage_meta.get("prompt_tokens", 0)
        completion_tokens = usage_meta.get("output_tokens") or usage_meta.get("completion_tokens", 0)
        total_tokens = usage_meta.get("total_tokens", prompt_tokens + completion_tokens)

        usage = AIUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
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
