"""Groq Cloud AI Provider Implementation.

Direct REST integration with Groq Cloud OpenAI-compatible endpoint
(https://api.groq.com/openai/v1/chat/completions) supporting JSON object
structured outputs, ultra-fast inference, and token usage metrics.
"""

import json
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

logger = logging.getLogger("ai_provider.groq")


class GroqProvider(BaseAIProvider):
    """Groq Cloud integration using the OpenAI-compatible chat completions API."""

    API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        # Resolve key from GROQ_API_KEY or fallback to XAI_API_KEY if it has 'gsk_' prefix
        resolved_key = api_key or getattr(settings, "GROQ_API_KEY", None)
        if not resolved_key and getattr(settings, "XAI_API_KEY", None):
            xai_k = settings.XAI_API_KEY.strip()
            if xai_k.startswith("gsk_"):
                resolved_key = xai_k

        resolved_model = model or getattr(settings, "GROQ_MODEL", None) or "qwen/qwen3.8-27b"

        super().__init__(
            name="groq",
            default_model=resolved_model,
            timeout_seconds=timeout_seconds or settings.AI_REQUEST_TIMEOUT,
        )
        self.api_key = resolved_key
        self._client = client

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def map_http_error(self, e: httpx.HTTPStatusError) -> AIProviderError:
        """Provider-specific mapping of Groq error payloads."""
        status = e.response.status_code
        retry_after = parse_retry_after(e.response)

        try:
            body = e.response.json()
            error_obj = body.get("error", {})
            err_msg = str(error_obj.get("message") or body)
            err_code = str(error_obj.get("code") or "")
            err_type = str(error_obj.get("type") or "")
        except Exception:
            err_msg = e.response.text[:200]
            err_code = ""
            err_type = ""

        lower_msg = err_msg.lower()

        # 401 Authentication Error
        if (
            status == 401
            or err_code == "invalid_api_key"
            or "invalid api key" in lower_msg
            or "unauthorized" in lower_msg
        ):
            return AIProviderAuthError(
                message=f"Groq Cloud authentication failed: {err_msg}",
                provider=self.name,
                status_code=status,
            )

        # 402 / Quota / Rate limit
        if status == 402 or "quota" in lower_msg or "rate limit" in lower_msg:
            return AIProviderRateLimitError(
                message=f"Groq Cloud rate limit or quota exceeded: {err_msg}",
                provider=self.name,
                status_code=status,
                retry_after=retry_after,
            )

        if status == 429:
            return AIProviderRateLimitError(
                message=f"Groq Cloud rate limit: {err_msg}",
                provider=self.name,
                status_code=status,
                retry_after=retry_after,
            )

        # 400 Invalid Request
        if status == 400:
            return AIProviderInvalidRequestError(
                message=f"Groq Cloud invalid request: {err_msg}",
                provider=self.name,
                status_code=status,
            )

        # 5xx Unavailable
        if status >= 500:
            return AIProviderUnavailableError(
                message=f"Groq Cloud unavailable ({status}): {err_msg}",
                provider=self.name,
                status_code=status,
                retry_after=retry_after,
            )

        return AIProviderError(
            message=f"Groq Cloud HTTP {status}: {err_msg}",
            provider=self.name,
            status_code=status,
            retry_after=retry_after,
        )

    def _prepare_payload(self, request: AIRequest) -> Dict[str, Any]:
        messages = []

        system_content = request.system_instruction or "You are an AI assistant."
        if request.response_schema is not None:
            schema_json = json.dumps(request.response_schema.model_json_schema())
            system_content += (
                f"\n\nYou MUST return valid JSON adhering strictly to this JSON schema:\n{schema_json}\n"
                "Do not include any explanation or markdown formatting, output ONLY the JSON object."
            )

        messages.append({"role": "system", "content": system_content})
        messages.append({"role": "user", "content": request.prompt})

        payload: Dict[str, Any] = {
            "model": self.default_model,
            "messages": messages,
            "temperature": request.temperature,
        }

        if request.max_output_tokens:
            payload["max_tokens"] = request.max_output_tokens

        if request.response_schema is not None:
            payload["response_format"] = {"type": "json_object"}

        return payload

    async def generate(self, request: AIRequest) -> AIResponse:
        """Execute request against Groq Cloud API."""
        if not self.is_configured:
            raise AIProviderAuthError(
                message="Groq Cloud API key is not configured",
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
                    message=f"Groq request timed out after {self._timeout_seconds}s: {str(te)}",
                    provider=self.name,
                ) from te
            except httpx.HTTPStatusError as hse:
                raise self.map_http_error(hse) from hse
            except httpx.RequestError as re:
                raise AIProviderUnavailableError(
                    message=f"Groq connection error: {str(re)}",
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
                        message=f"Groq request timed out after {self._timeout_seconds}s: {str(te)}",
                        provider=self.name,
                    ) from te
                except httpx.HTTPStatusError as hse:
                    raise self.map_http_error(hse) from hse
                except httpx.RequestError as re:
                    raise AIProviderUnavailableError(
                        message=f"Groq connection error: {str(re)}",
                        provider=self.name,
                    ) from re

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        try:
            data = response.json()
        except Exception as e:
            raise AIProviderError(
                message=f"Groq returned unparseable JSON payload: {str(e)}",
                provider=self.name,
            ) from e

        choices = data.get("choices", [])
        if not choices:
            raise AIProviderError(
                message="Groq returned empty choices in response",
                provider=self.name,
            )

        content = choices[0].get("message", {}).get("content", "")

        usage_data = data.get("usage", {})
        usage = AIUsage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        parsed_json, structured = self.validate_and_parse_response(
            content, request.response_schema
        )

        return AIResponse(
            content=content,
            raw_json=parsed_json,
            structured_data=structured,
            provider=self.name,
            model=data.get("model", self.default_model),
            latency_ms=round(latency_ms, 2),
            usage=usage,
            correlation_id=request.correlation_id,
        )
