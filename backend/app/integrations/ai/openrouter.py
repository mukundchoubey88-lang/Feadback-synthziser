"""OpenRouter AI Provider Implementation.

Direct REST integration with OpenRouter /api/v1/chat/completions endpoint
supporting explicit fallback models array, structured outputs, and token/cost usage.

COST & ROUTING SPECIFICATIONS:
- Primary default model: `google/gemini-2.0-flash-001`
  Cost: ~$0.10/M prompt, ~$0.40/M completion. Best balance of speed, cost, and JSON schema fidelity.
- Approved fallback models:
  1. `meta-llama/llama-3.3-70b-instruct`
     Cost: ~$0.13/M prompt, ~$0.40/M completion. Cost-effective open-weights model matching Gemini economics.
  2. `anthropic/claude-3.5-haiku`
     Cost: ~$0.80/M prompt, ~$4.00/M completion (~8-10x cost of Gemini). High reasoning fallback.
- Never silently selects unapproved models.
"""

import logging
import time
from typing import Any, Dict, List, Optional
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

logger = logging.getLogger("ai_provider.openrouter")

# Registry of models verified to reliably support JSON schema / strict structured outputs on OpenRouter
STRUCTURED_OUTPUT_CAPABLE_MODELS = {
    "google/gemini-2.0-flash-001",
    "google/gemini-flash-1.5",
    "google/gemini-pro-1.5",
    "anthropic/claude-3.5-haiku",
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "meta-llama/llama-3.3-70b-instruct",
    "mistralai/mistral-large-2407",
    "xiaomi/mimo-v2.6-flash",
    "xiaomi/mimo-v2.6-pro",
}


class OpenRouterProvider(BaseAIProvider):
    """OpenRouter integration via /api/v1/chat/completions."""

    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        timeout_seconds: Optional[float] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(
            name="openrouter",
            default_model=model or settings.OPENROUTER_MODEL or "google/gemini-2.0-flash-001",
            timeout_seconds=timeout_seconds or settings.AI_REQUEST_TIMEOUT,
        )
        self.api_key = api_key if api_key is not None else settings.OPENROUTER_API_KEY
        if fallback_models is not None:
            self.fallback_models = fallback_models
        else:
            self.fallback_models = settings.openrouter_fallback_models_list
        self._client = client

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def map_http_error(self, e: httpx.HTTPStatusError) -> AIProviderError:
        """Provider-specific mapping of OpenRouter error payloads.

        Interprets OpenRouter error status, error code, and metadata reasons
        to distinguish insufficient credits/payment exhaustion from transient
        rate limits and invalid keys.
        """
        status = e.response.status_code
        retry_after = parse_retry_after(e.response)

        try:
            body = e.response.json()
            error_obj = body.get("error", {})
            err_msg = str(error_obj.get("message") or body)
            err_code = error_obj.get("code")
            metadata = error_obj.get("metadata", {})
            reasons = metadata.get("reasons", []) if isinstance(metadata, dict) else []
        except Exception:
            err_msg = e.response.text[:200]
            err_code = None
            reasons = []

        lower_msg = err_msg.lower()

        # 402 Payment Required or Insufficient Credits
        is_payment_exhausted = (
            status == 402
            or err_code == 402
            or "insufficient_credits" in reasons
            or "insufficient credits" in lower_msg
            or "credit" in lower_msg
            or "balance" in lower_msg
            or "payment" in lower_msg
        )
        if is_payment_exhausted:
            return AIProviderQuotaExhaustedError(
                message=f"OpenRouter credits/payment exhausted: {err_msg}",
                provider=self.name,
                status_code=status,
                retry_after=retry_after,
            )

        # 401 Unauthorized / Invalid Key
        if (
            status == 401
            or err_code == 401
            or "unauthorized" in lower_msg
            or "invalid api key" in lower_msg
        ):
            return AIProviderAuthError(
                message=f"OpenRouter authentication failed: {err_msg}",
                provider=self.name,
                status_code=status,
            )

        # 403 Forbidden
        if status == 403 or err_code == 403:
            if "credit" in lower_msg or "balance" in lower_msg:
                return AIProviderQuotaExhaustedError(
                    message=f"OpenRouter credit restriction: {err_msg}",
                    provider=self.name,
                    status_code=status,
                )
            return AIProviderAuthError(
                message=f"OpenRouter authorization forbidden: {err_msg}",
                provider=self.name,
                status_code=status,
            )

        # 429 Rate Limiting
        if status == 429 or err_code == 429:
            if "credit" in lower_msg or "balance" in lower_msg:
                return AIProviderQuotaExhaustedError(
                    message=f"OpenRouter credit limit exhausted (429): {err_msg}",
                    provider=self.name,
                    status_code=status,
                    retry_after=retry_after,
                )
            return AIProviderRateLimitError(
                message=f"OpenRouter rate limit: {err_msg}",
                provider=self.name,
                status_code=status,
                retry_after=retry_after,
            )

        # 400 Bad Request
        if status == 400 or err_code == 400:
            return AIProviderInvalidRequestError(
                message=f"OpenRouter invalid request: {err_msg}",
                provider=self.name,
                status_code=status,
            )

        # 5xx Provider Unavailable
        if status >= 500:
            return AIProviderUnavailableError(
                message=f"OpenRouter unavailable ({status}): {err_msg}",
                provider=self.name,
                status_code=status,
                retry_after=retry_after,
            )

        return AIProviderError(
            message=f"OpenRouter HTTP {status}: {err_msg}",
            provider=self.name,
            status_code=status,
            retry_after=retry_after,
        )

    def _prepare_payload(self, request: AIRequest) -> Dict[str, Any]:
        messages = []
        if request.system_instruction:
            messages.append({"role": "system", "content": request.system_instruction})
        messages.append({"role": "user", "content": request.prompt})

        payload: Dict[str, Any] = {
            "model": self.default_model,
            "messages": messages,
            "temperature": request.temperature,
        }

        # Build approved models routing list
        models_list = [self.default_model]
        if self.fallback_models:
            for fb in self.fallback_models:
                if fb not in models_list:
                    models_list.append(fb)

        # Priority 3: When structured outputs are required, enforce that all routed models
        # are verified for JSON Schema structured output compatibility.
        if request.response_schema is not None:
            filtered_models = [
                m for m in models_list if m in STRUCTURED_OUTPUT_CAPABLE_MODELS
            ]
            if not filtered_models:
                # If neither the default nor any fallback is in the known list, retain default and warn
                logger.warning(
                    "Default model '%s' not in known structured output registry; proceeding with default.",
                    self.default_model,
                )
                filtered_models = [self.default_model]
            models_list = filtered_models

            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.response_schema.__name__,
                    "strict": True,
                    "schema": request.response_schema.model_json_schema(),
                },
            }

        # Only pass models array if more than 1 model is specified or fallbacks exist
        if len(models_list) > 1 or self.fallback_models:
            payload["models"] = models_list[:3]

        if request.max_output_tokens:
            payload["max_tokens"] = request.max_output_tokens

        return payload

    async def generate(self, request: AIRequest) -> AIResponse:
        """Execute request against OpenRouter API."""
        if not self.is_configured:
            raise AIProviderAuthError(
                message="OpenRouter API key is not configured",
                provider=self.name,
                status_code=401,
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/feedback-synthesizer",
            "X-Title": "Feedback Intelligence Agent",
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
                    message=f"OpenRouter request timed out after {self._timeout_seconds}s: {str(te)}",
                    provider=self.name,
                ) from te
            except httpx.HTTPStatusError as hse:
                raise self.map_http_error(hse) from hse
            except httpx.RequestError as re:
                raise AIProviderUnavailableError(
                    message=f"OpenRouter connection error: {str(re)}",
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
                        message=f"OpenRouter request timed out after {self._timeout_seconds}s: {str(te)}",
                        provider=self.name,
                    ) from te
                except httpx.HTTPStatusError as hse:
                    raise self.map_http_error(hse) from hse
                except httpx.RequestError as re:
                    raise AIProviderUnavailableError(
                        message=f"OpenRouter connection error: {str(re)}",
                        provider=self.name,
                    ) from re

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        data = response.json()

        choices = data.get("choices", [])
        if not choices:
            raise AIProviderUnavailableError(
                message="OpenRouter returned no choices in response",
                provider=self.name,
            )

        raw_text = choices[0].get("message", {}).get("content", "")
        actual_model = data.get("model", self.default_model)

        # Audit check: verify actual_model is within approved configured set
        approved_models = [self.default_model] + (self.fallback_models or [])
        if approved_models and actual_model not in approved_models:
            logger.warning(
                "OpenRouter returned model '%s' which was not in explicitly approved list: %s",
                actual_model,
                approved_models,
            )

        # Extract token usage and cost if provided
        usage_meta = data.get("usage", {})
        cost_val = usage_meta.get("total_cost") or usage_meta.get("cost")
        cost_usd = float(cost_val) if cost_val is not None else None

        usage = AIUsage(
            prompt_tokens=usage_meta.get("prompt_tokens", 0),
            completion_tokens=usage_meta.get("completion_tokens", 0),
            total_tokens=usage_meta.get("total_tokens", 0),
            cost_usd=cost_usd,
        )

        parsed_json, structured = self.validate_and_parse_response(
            raw_text, request.response_schema
        )

        return AIResponse(
            content=raw_text,
            raw_json=parsed_json,
            structured_data=structured,
            provider=self.name,
            model=actual_model,
            latency_ms=round(latency_ms, 2),
            usage=usage,
            correlation_id=request.correlation_id,
        )
