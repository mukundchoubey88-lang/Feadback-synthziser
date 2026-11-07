"""Comprehensive Tests for Multi-Provider AI Integration & Automatic Failover.

Tests Gemini, OpenRouter, and xAI Grok provider integrations, circuit breaking,
transient retry handling, Retry-After parsing, fallback chains, schema validation,
privacy safeguards, and error hierarchies using 100% mocked transports.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict
import httpx
import pytest
from pydantic import BaseModel, Field

from app.integrations.ai.base import parse_retry_after
from app.integrations.ai.circuit_breaker import AIProviderCircuitBreaker
from app.integrations.ai.exceptions import (
    AIProviderAuthError,
    AIProviderError,
    AIProviderInvalidRequestError,
    AIProviderQuotaExhaustedError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    AIProviderValidationError,
    AllAIProvidersFailedError,
)
from app.integrations.ai.gemini import GeminiProvider
from app.integrations.ai.grok import GrokProvider
from app.integrations.ai.manager import AIProviderManager
from app.integrations.ai.openrouter import OpenRouterProvider
from app.integrations.ai.schemas import AIRequest, AIResponse, AIUsage


# --- Sample Pydantic Schemas for Structured Output Testing ---


class FeedbackCategoryModel(BaseModel):
    category: str = Field(..., description="Classification category")
    sentiment: str = Field(..., description="Sentiment score: positive, neutral, negative")
    confidence: float = Field(..., ge=0.0, le=1.0)


# --- Helper Mock Handlers ---


def make_gemini_response(
    text: str = '{"category": "bug", "sentiment": "negative", "confidence": 0.95}',
    status_code: int = 200,
    headers: Dict[str, str] = None,
) -> httpx.Response:
    if status_code != 200:
        return httpx.Response(
            status_code=status_code,
            headers=headers or {},
            json={"error": {"code": status_code, "message": f"Gemini error {status_code}"}},
        )
    return httpx.Response(
        status_code=200,
        headers=headers or {},
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": text}],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 42,
                "candidatesTokenCount": 18,
                "totalTokenCount": 60,
            },
        },
    )


def make_openrouter_response(
    text: str = '{"category": "bug", "sentiment": "negative", "confidence": 0.95}',
    model: str = "google/gemini-2.0-flash-001",
    status_code: int = 200,
    headers: Dict[str, str] = None,
) -> httpx.Response:
    if status_code != 200:
        return httpx.Response(
            status_code=status_code,
            headers=headers or {},
            json={"error": {"code": status_code, "message": f"OpenRouter error {status_code}"}},
        )
    return httpx.Response(
        status_code=200,
        headers=headers or {},
        json={
            "id": "gen-openrouter-123",
            "model": model,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": text,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 40,
                "completion_tokens": 15,
                "total_tokens": 55,
                "total_cost": 0.00015,
            },
        },
    )


def make_grok_response(
    text: str = '{"category": "bug", "sentiment": "negative", "confidence": 0.95}',
    model: str = "grok-4.7",
    status_code: int = 200,
    headers: Dict[str, str] = None,
) -> httpx.Response:
    if status_code != 200:
        return httpx.Response(
            status_code=status_code,
            headers=headers or {},
            json={"error": {"code": status_code, "message": f"xAI Grok error {status_code}"}},
        )
    return httpx.Response(
        status_code=200,
        headers=headers or {},
        json={
            "id": "resp-grok-456",
            "model": model,
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": text,
                        }
                    ],
                }
            ],
            "usage": {
                "input_tokens": 45,
                "output_tokens": 20,
                "total_tokens": 65,
            },
        },
    )


# ============================================================================
# 1. Base Provider & Retry-After Tests
# ============================================================================


def test_parse_retry_after_integer():
    resp = httpx.Response(status_code=429, headers={"Retry-After": "45"})
    assert parse_retry_after(resp) == 45.0


def test_parse_retry_after_missing():
    resp = httpx.Response(status_code=429, headers={})
    assert parse_retry_after(resp) is None
    assert parse_retry_after(None) is None


def test_parse_retry_after_case_insensitive():
    resp = httpx.Response(status_code=429, headers={"retry-after": "12.5"})
    assert parse_retry_after(resp) == 12.5


# ============================================================================
# 2. Circuit Breaker Unit Tests
# ============================================================================


def test_circuit_breaker_lifecycle():
    cb = AIProviderCircuitBreaker(default_cooldown_seconds=10.0)

    # Initial state
    assert cb.is_available("gemini") is True

    # Record failure
    cb.record_failure("gemini", cooldown_seconds=5.0)
    assert cb.is_available("gemini") is False

    status = cb.get_status()
    assert status["gemini"]["available"] is False
    assert status["gemini"]["in_cooldown"] is True
    assert status["gemini"]["failure_count"] == 1

    # Record success resets
    cb.record_success("gemini")
    assert cb.is_available("gemini") is True
    assert cb.get_status()["gemini"]["failure_count"] == 0


def test_circuit_breaker_disable():
    cb = AIProviderCircuitBreaker()
    cb.disable_provider("grok", "API key missing")
    assert cb.is_available("grok") is False
    status = cb.get_status()
    assert status["grok"]["is_disabled"] is True
    assert status["grok"]["disabled_reason"] == "API key missing"


def test_circuit_breaker_cooldown_expiration():
    cb = AIProviderCircuitBreaker(default_cooldown_seconds=0.1)
    cb.record_failure("openrouter", cooldown_seconds=0.1)
    assert cb.is_available("openrouter") is False

    time.sleep(0.15)
    # Expired, probe allowed
    assert cb.is_available("openrouter") is True


# ============================================================================
# 3. Provider Direct Generation Tests
# ============================================================================


@pytest.mark.anyio
async def test_gemini_provider_direct_success():
    def handler(request: httpx.Request):
        assert "x-goog-api-key" in request.headers
        assert request.headers["x-goog-api-key"] == "test-gemini-key"
        return make_gemini_response()

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    provider = GeminiProvider(api_key="test-gemini-key", client=client)

    req = AIRequest(
        prompt="Classify this feedback",
        response_schema=FeedbackCategoryModel,
        correlation_id="cid-101",
    )
    res = await provider.generate(req)

    assert res.provider == "gemini"
    assert res.model == provider.default_model
    assert res.structured_data is not None
    assert isinstance(res.structured_data, FeedbackCategoryModel)
    assert res.structured_data.category == "bug"
    assert res.usage.prompt_tokens == 42
    assert res.correlation_id == "cid-101"


@pytest.mark.anyio
async def test_openrouter_provider_direct_success():
    def handler(request: httpx.Request):
        assert request.headers.get("Authorization") == "Bearer test-openrouter-key"
        body = json.loads(request.read())
        assert "models" in body  # Explicit fallback models array
        return make_openrouter_response()

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    provider = OpenRouterProvider(
        api_key="test-openrouter-key",
        fallback_models=["anthropic/claude-3.5-haiku"],
        client=client,
    )

    req = AIRequest(
        prompt="Classify this feedback",
        response_schema=FeedbackCategoryModel,
    )
    res = await provider.generate(req)

    assert res.provider == "openrouter"
    assert res.structured_data.category == "bug"
    assert res.usage.cost_usd == 0.00015


@pytest.mark.anyio
async def test_grok_provider_direct_success():
    def handler(request: httpx.Request):
        assert request.headers.get("Authorization") == "Bearer test-grok-key"
        body = json.loads(request.read())
        assert "input" in body
        assert "text" in body  # Responses API format
        return make_grok_response()

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    provider = GrokProvider(api_key="test-grok-key", client=client)

    req = AIRequest(
        prompt="Classify this feedback",
        response_schema=FeedbackCategoryModel,
    )
    res = await provider.generate(req)

    assert res.provider == "grok"
    assert res.structured_data.category == "bug"
    assert res.usage.total_tokens == 65


# ============================================================================
# 4. Failover & Resilience Tests in AIProviderManager
# ============================================================================


@pytest.mark.anyio
async def test_manager_gemini_success_no_fallback():
    gemini_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_gemini_response())
    )
    openrouter_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: pytest.fail("OpenRouter should not be called"))
    )

    gemini_prov = GeminiProvider(api_key="key1", client=gemini_client)
    openrouter_prov = OpenRouterProvider(api_key="key2", client=openrouter_client)

    manager = AIProviderManager(
        providers={"gemini": gemini_prov, "openrouter": openrouter_prov},
        priority_order=["gemini", "openrouter"],
    )

    req = AIRequest(prompt="Classify feedback", response_schema=FeedbackCategoryModel)
    resp = await manager.generate(req)

    assert resp.provider == "gemini"
    assert resp.structured_data.sentiment == "negative"


@pytest.mark.anyio
async def test_manager_gemini_quota_exhausted_failover_to_openrouter():
    """Gemini returns 429 quota exhausted; manager immediately falls over to OpenRouter."""
    gemini_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(
                429,
                json={"error": {"code": 429, "message": "Resource has been exhausted (quota limit reached)"}},
            )
        )
    )
    openrouter_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_openrouter_response())
    )

    gemini_prov = GeminiProvider(api_key="key1", client=gemini_client)
    openrouter_prov = OpenRouterProvider(api_key="key2", client=openrouter_client)

    manager = AIProviderManager(
        providers={"gemini": gemini_prov, "openrouter": openrouter_prov},
        priority_order=["gemini", "openrouter"],
    )

    req = AIRequest(prompt="Classify feedback", response_schema=FeedbackCategoryModel)
    resp = await manager.generate(req)

    assert resp.provider == "openrouter"
    # Check circuit breaker put Gemini into cooldown
    assert manager.circuit_breaker.is_available("gemini") is False


@pytest.mark.anyio
async def test_manager_gemini_timeout_fallback_to_openrouter():
    """Gemini times out; manager falls over to OpenRouter."""
    def timeout_handler(req: httpx.Request):
        raise httpx.ReadTimeout("Connection read timeout")

    gemini_client = httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler))
    openrouter_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_openrouter_response())
    )

    gemini_prov = GeminiProvider(api_key="key1", client=gemini_client)
    openrouter_prov = OpenRouterProvider(api_key="key2", client=openrouter_client)

    manager = AIProviderManager(
        providers={"gemini": gemini_prov, "openrouter": openrouter_prov},
        priority_order=["gemini", "openrouter"],
        max_retries_per_provider=0,  # Fall over after 0 retries
    )

    req = AIRequest(prompt="Classify feedback", response_schema=FeedbackCategoryModel)
    resp = await manager.generate(req)

    assert resp.provider == "openrouter"


@pytest.mark.anyio
async def test_manager_gemini_5xx_server_error_fallback():
    """Gemini 503 Service Unavailable triggers failover to OpenRouter."""
    gemini_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_gemini_response(status_code=503))
    )
    openrouter_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_openrouter_response())
    )

    gemini_prov = GeminiProvider(api_key="key1", client=gemini_client)
    openrouter_prov = OpenRouterProvider(api_key="key2", client=openrouter_client)

    manager = AIProviderManager(
        providers={"gemini": gemini_prov, "openrouter": openrouter_prov},
        priority_order=["gemini", "openrouter"],
        max_retries_per_provider=0,
    )

    req = AIRequest(prompt="Classify feedback", response_schema=FeedbackCategoryModel)
    resp = await manager.generate(req)

    assert resp.provider == "openrouter"


@pytest.mark.anyio
async def test_manager_openrouter_fails_grok_succeeds():
    """Gemini fails, OpenRouter fails (502), Grok tertiary succeeds."""
    gemini_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_gemini_response(status_code=500))
    )
    openrouter_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_openrouter_response(status_code=502))
    )
    grok_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_grok_response())
    )

    gemini_prov = GeminiProvider(api_key="key1", client=gemini_client)
    openrouter_prov = OpenRouterProvider(api_key="key2", client=openrouter_client)
    grok_prov = GrokProvider(api_key="key3", client=grok_client)

    manager = AIProviderManager(
        providers={"gemini": gemini_prov, "openrouter": openrouter_prov, "grok": grok_prov},
        priority_order=["gemini", "openrouter", "grok"],
        max_retries_per_provider=0,
    )

    req = AIRequest(prompt="Classify feedback", response_schema=FeedbackCategoryModel)
    resp = await manager.generate(req)

    assert resp.provider == "grok"


@pytest.mark.anyio
async def test_manager_all_providers_fail():
    """All providers fail -> raises AllAIProvidersFailedError with details."""
    gemini_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_gemini_response(status_code=503))
    )
    openrouter_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_openrouter_response(status_code=503))
    )
    grok_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_grok_response(status_code=503))
    )

    gemini_prov = GeminiProvider(api_key="key1", client=gemini_client)
    openrouter_prov = OpenRouterProvider(api_key="key2", client=openrouter_client)
    grok_prov = GrokProvider(api_key="key3", client=grok_client)

    manager = AIProviderManager(
        providers={"gemini": gemini_prov, "openrouter": openrouter_prov, "grok": grok_prov},
        priority_order=["gemini", "openrouter", "grok"],
        max_retries_per_provider=0,
    )

    req = AIRequest(prompt="Classify feedback")
    with pytest.raises(AllAIProvidersFailedError) as exc_info:
        await manager.generate(req)

    assert len(exc_info.value.failures) == 3


@pytest.mark.anyio
async def test_manager_invalid_credentials_logs_warning_and_falls_over():
    """Gemini 401 Unauthorized triggers safe fallback to OpenRouter."""
    gemini_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_gemini_response(status_code=401))
    )
    openrouter_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_openrouter_response())
    )

    gemini_prov = GeminiProvider(api_key="bad-key", client=gemini_client)
    openrouter_prov = OpenRouterProvider(api_key="good-key", client=openrouter_client)

    manager = AIProviderManager(
        providers={"gemini": gemini_prov, "openrouter": openrouter_prov},
        priority_order=["gemini", "openrouter"],
    )

    req = AIRequest(prompt="Classify feedback", response_schema=FeedbackCategoryModel)
    resp = await manager.generate(req)

    assert resp.provider == "openrouter"


@pytest.mark.anyio
async def test_manager_invalid_request_400_raises_immediately_no_fallback():
    """Client-side 400 Bad Request raises AIProviderInvalidRequestError immediately without fallback."""
    gemini_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_gemini_response(status_code=400))
    )
    openrouter_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: pytest.fail("OpenRouter must not be called on 400"))
    )

    gemini_prov = GeminiProvider(api_key="key1", client=gemini_client)
    openrouter_prov = OpenRouterProvider(api_key="key2", client=openrouter_client)

    manager = AIProviderManager(
        providers={"gemini": gemini_prov, "openrouter": openrouter_prov},
        priority_order=["gemini", "openrouter"],
    )

    req = AIRequest(prompt="Malformed prompt")
    with pytest.raises(AIProviderInvalidRequestError):
        await manager.generate(req)


@pytest.mark.anyio
async def test_manager_malformed_json_fallback():
    """Gemini returns unparseable JSON; manager falls over to OpenRouter."""
    gemini_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_gemini_response(text="NOT_VALID_JSON{"))
    )
    openrouter_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_openrouter_response())
    )

    gemini_prov = GeminiProvider(api_key="key1", client=gemini_client)
    openrouter_prov = OpenRouterProvider(api_key="key2", client=openrouter_client)

    manager = AIProviderManager(
        providers={"gemini": gemini_prov, "openrouter": openrouter_prov},
        priority_order=["gemini", "openrouter"],
        max_retries_per_provider=0,
    )

    req = AIRequest(prompt="Classify feedback", response_schema=FeedbackCategoryModel)
    resp = await manager.generate(req)

    assert resp.provider == "openrouter"
    assert resp.structured_data.category == "bug"


@pytest.mark.anyio
async def test_manager_circuit_breaker_skips_cooldown_provider():
    """Provider currently in circuit breaker cooldown is skipped immediately."""
    call_count = {"gemini": 0}

    def gemini_handler(req: httpx.Request):
        call_count["gemini"] += 1
        return make_gemini_response()

    gemini_client = httpx.AsyncClient(transport=httpx.MockTransport(gemini_handler))
    openrouter_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_openrouter_response())
    )

    gemini_prov = GeminiProvider(api_key="key1", client=gemini_client)
    openrouter_prov = OpenRouterProvider(api_key="key2", client=openrouter_client)

    manager = AIProviderManager(
        providers={"gemini": gemini_prov, "openrouter": openrouter_prov},
        priority_order=["gemini", "openrouter"],
    )

    # Manually put Gemini in cooldown
    manager.circuit_breaker.record_failure("gemini", cooldown_seconds=60.0)

    req = AIRequest(prompt="Classify feedback", response_schema=FeedbackCategoryModel)
    resp = await manager.generate(req)

    assert resp.provider == "openrouter"
    assert call_count["gemini"] == 0  # Gemini never touched


@pytest.mark.anyio
async def test_manager_missing_optional_provider_key_does_not_block():
    """Unconfigured Grok provider is safely skipped, Gemini succeeds."""
    gemini_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: make_gemini_response())
    )

    gemini_prov = GeminiProvider(api_key="key1", client=gemini_client)
    grok_prov = GrokProvider(api_key="")  # Explicitly unconfigured

    manager = AIProviderManager(
        providers={"gemini": gemini_prov, "grok": grok_prov},
        priority_order=["gemini", "grok"],
    )

    req = AIRequest(prompt="Classify feedback", response_schema=FeedbackCategoryModel)
    resp = await manager.generate(req)

    assert resp.provider == "gemini"


@pytest.mark.anyio
async def test_manager_all_provider_keys_missing_raises_clear_error():
    """If no providers have API keys configured, raises AIProviderAuthError immediately."""
    gemini_prov = GeminiProvider(api_key="")
    openrouter_prov = OpenRouterProvider(api_key="")
    grok_prov = GrokProvider(api_key="")

    manager = AIProviderManager(
        providers={"gemini": gemini_prov, "openrouter": openrouter_prov, "grok": grok_prov},
        priority_order=["gemini", "openrouter", "grok"],
    )

    req = AIRequest(prompt="Classify feedback")
    with pytest.raises(AIProviderAuthError) as exc_info:
        await manager.generate(req)

    assert "No AI providers are configured" in str(exc_info.value)


@pytest.mark.anyio
async def test_privacy_zero_raw_feedback_or_secrets_in_logs(caplog):
    """Verify that sensitive raw feedback and API keys are NEVER logged."""
    sensitive_prompt = "User said: My private SSN is 000-11-2222 and password is SECRET_PASS!"
    secret_api_key = "super-secret-api-key-xyz"

    def gemini_handler(req: httpx.Request):
        return make_gemini_response()

    gemini_client = httpx.AsyncClient(transport=httpx.MockTransport(gemini_handler))
    gemini_prov = GeminiProvider(api_key=secret_api_key, client=gemini_client)

    manager = AIProviderManager(
        providers={"gemini": gemini_prov},
        priority_order=["gemini"],
    )

    req = AIRequest(prompt=sensitive_prompt, correlation_id="cid-privacy-check")
    with caplog.at_level(logging.DEBUG):
        await manager.generate(req)

    # Assert no secret key or sensitive prompt in any log record
    for record in caplog.records:
        assert secret_api_key not in record.message
        assert "000-11-2222" not in record.message
        assert "SECRET_PASS" not in record.message


@pytest.mark.anyio
async def test_async_cancellation_behavior():
    """Verify that cancelling an ongoing request cleans up promptly."""
    async def slow_handler(req: httpx.Request):
        await asyncio.sleep(5.0)
        return make_gemini_response()

    gemini_client = httpx.AsyncClient(transport=httpx.MockTransport(slow_handler))
    gemini_prov = GeminiProvider(api_key="key1", client=gemini_client)

    manager = AIProviderManager(
        providers={"gemini": gemini_prov},
        priority_order=["gemini"],
    )

    req = AIRequest(prompt="Test prompt")
    task = asyncio.create_task(manager.generate(req))
    await asyncio.sleep(0.05)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


# ============================================================================
# 5. Part 5.2 Corrective Audit Tests
# ============================================================================


def test_gemini_daily_quota_exhaustion_429():
    """Verify Gemini 429 with daily quota/spend limit is classified as QuotaExhausted."""
    prov = GeminiProvider(api_key="test-key")
    resp = httpx.Response(
        status_code=429,
        json={
            "error": {
                "code": 429,
                "message": "Resource has been exhausted (e.g. check quota). Daily quota exceeded.",
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                        "reason": "QUOTA_EXCEEDED",
                        "metadata": {
                            "quota_limit": "GenerateContentRequestsPerDayPerProject",
                        },
                    }
                ],
            }
        },
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )
    exc = httpx.HTTPStatusError("429 error", request=resp.request, response=resp)
    mapped = prov.map_http_error(exc)
    assert isinstance(mapped, AIProviderQuotaExhaustedError)
    assert mapped.is_transient is False


def test_gemini_temporary_rate_limit_429():
    """Verify Gemini 429 with RPM/TPM is classified as retryable RateLimitError."""
    prov = GeminiProvider(api_key="test-key")
    resp = httpx.Response(
        status_code=429,
        headers={"Retry-After": "20"},
        json={
            "error": {
                "code": 429,
                "message": "Resource has been exhausted (per minute limit).",
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                        "reason": "RATE_LIMIT_EXCEEDED",
                        "metadata": {
                            "quota_limit": "GenerateContentRequestsPerMinutePerProject",
                        },
                    }
                ],
            }
        },
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )
    exc = httpx.HTTPStatusError("429 error", request=resp.request, response=resp)
    mapped = prov.map_http_error(exc)
    assert isinstance(mapped, AIProviderRateLimitError)
    assert mapped.is_transient is True
    assert mapped.retry_after == 20.0


def test_gemini_403_permission_denied_distinction():
    """Verify Gemini 403 distinguishes invalid key, suspended project, and ambiguous."""
    prov = GeminiProvider(api_key="test-key")

    # Case A: API Key Invalid
    resp_key = httpx.Response(
        status_code=403,
        json={
            "error": {
                "code": 403,
                "message": "API key not valid. Please pass a valid API key.",
                "status": "PERMISSION_DENIED",
                "details": [{"reason": "API_KEY_INVALID"}],
            }
        },
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )
    mapped_key = prov.map_http_error(httpx.HTTPStatusError("403", request=resp_key.request, response=resp_key))
    assert isinstance(mapped_key, AIProviderAuthError)

    # Case B: Project Billing Suspended
    resp_bill = httpx.Response(
        status_code=403,
        json={
            "error": {
                "code": 403,
                "message": "Project billing has been disabled.",
                "status": "PERMISSION_DENIED",
                "details": [{"reason": "CONSUMER_SUSPENDED"}],
            }
        },
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )
    mapped_bill = prov.map_http_error(httpx.HTTPStatusError("403", request=resp_bill.request, response=resp_bill))
    assert isinstance(mapped_bill, AIProviderQuotaExhaustedError)

    # Case C: Ambiguous 403 (conservative safe classification as AuthError)
    resp_ambig = httpx.Response(
        status_code=403,
        json={"error": {"code": 403, "message": "The caller does not have permission"}},
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )
    mapped_ambig = prov.map_http_error(httpx.HTTPStatusError("403", request=resp_ambig.request, response=resp_ambig))
    assert isinstance(mapped_ambig, AIProviderAuthError)


def test_gemini_invalid_api_key_400():
    """Verify Gemini 400 with API key error is mapped to AuthError rather than InvalidRequest."""
    prov = GeminiProvider(api_key="test-key")
    resp = httpx.Response(
        status_code=400,
        json={
            "error": {
                "code": 400,
                "message": "API key not valid. Please pass a valid API key.",
                "status": "INVALID_ARGUMENT",
            }
        },
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )
    exc = httpx.HTTPStatusError("400 error", request=resp.request, response=resp)
    mapped = prov.map_http_error(exc)
    assert isinstance(mapped, AIProviderAuthError)


def test_openrouter_insufficient_credits_402():
    """Verify OpenRouter 402 / insufficient credits is mapped to QuotaExhausted."""
    prov = OpenRouterProvider(api_key="test-key")
    resp = httpx.Response(
        status_code=402,
        json={
            "error": {
                "code": 402,
                "message": "User has insufficient credits to complete request.",
                "metadata": {"reasons": ["insufficient_credits"]},
            }
        },
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )
    exc = httpx.HTTPStatusError("402 error", request=resp.request, response=resp)
    mapped = prov.map_http_error(exc)
    assert isinstance(mapped, AIProviderQuotaExhaustedError)
    assert mapped.is_transient is False


def test_openrouter_rate_limiting_429():
    """Verify OpenRouter 429 rate limit is mapped to RateLimitError."""
    prov = OpenRouterProvider(api_key="test-key")
    resp = httpx.Response(
        status_code=429,
        headers={"Retry-After": "15"},
        json={"error": {"code": 429, "message": "Rate limit exceeded for model"}},
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )
    exc = httpx.HTTPStatusError("429 error", request=resp.request, response=resp)
    mapped = prov.map_http_error(exc)
    assert isinstance(mapped, AIProviderRateLimitError)
    assert mapped.is_transient is True
    assert mapped.retry_after == 15.0


def test_xai_authentication_and_rate_limit_failures():
    """Verify xAI Grok error payload interpretations."""
    prov = GrokProvider(api_key="test-key")

    # 401 Invalid Key
    resp_auth = httpx.Response(
        status_code=401,
        json={
            "error": {
                "message": "Incorrect API key provided",
                "type": "authentication_error",
                "code": "invalid_api_key",
            }
        },
        request=httpx.Request("POST", "https://api.x.ai/v1/responses"),
    )
    mapped_auth = prov.map_http_error(httpx.HTTPStatusError("401", request=resp_auth.request, response=resp_auth))
    assert isinstance(mapped_auth, AIProviderAuthError)

    # 429 Quota Exceeded
    resp_quota = httpx.Response(
        status_code=429,
        json={
            "error": {
                "message": "You have exceeded your current quota, please check plan.",
                "type": "insufficient_quota",
                "code": "insufficient_quota",
            }
        },
        request=httpx.Request("POST", "https://api.x.ai/v1/responses"),
    )
    mapped_quota = prov.map_http_error(httpx.HTTPStatusError("429", request=resp_quota.request, response=resp_quota))
    assert isinstance(mapped_quota, AIProviderQuotaExhaustedError)

    # 429 Temporary Rate Limit
    resp_rate = httpx.Response(
        status_code=429,
        json={
            "error": {
                "message": "Too many requests per second.",
                "type": "rate_limit_error",
            }
        },
        request=httpx.Request("POST", "https://api.x.ai/v1/responses"),
    )
    mapped_rate = prov.map_http_error(httpx.HTTPStatusError("429", request=resp_rate.request, response=resp_rate))
    assert isinstance(mapped_rate, AIProviderRateLimitError)


def test_unknown_or_ambiguous_provider_error_payload():
    """Verify BaseAIProvider.map_http_error safe fallback handling."""
    from app.integrations.ai.base import BaseAIProvider

    class DummyProvider(BaseAIProvider):
        @property
        def is_configured(self) -> bool:
            return True

        async def generate(self, req):
            raise NotImplementedError

    dummy = DummyProvider(name="dummy", default_model="dummy-v1")
    resp = httpx.Response(
        status_code=403,
        text="Unparseable HTML or gateway forbidden error",
        request=httpx.Request("POST", "https://dummy.example.com"),
    )
    exc = httpx.HTTPStatusError("403", request=resp.request, response=resp)
    mapped = dummy.map_http_error(exc)
    assert isinstance(mapped, AIProviderAuthError)


@pytest.mark.anyio
async def test_fallback_without_unnecessary_retries_on_quota_exhaustion():
    """Verify manager makes exactly 1 attempt on quota exhaustion before immediate fallback."""
    gemini_calls = 0

    def gemini_handler(req: httpx.Request):
        nonlocal gemini_calls
        gemini_calls += 1
        return httpx.Response(
            status_code=429,
            json={
                "error": {
                    "code": 429,
                    "message": "Daily quota limit reached",
                    "status": "RESOURCE_EXHAUSTED",
                    "details": [{"reason": "QUOTA_EXCEEDED"}],
                }
            },
        )

    openrouter_calls = 0

    def openrouter_handler(req: httpx.Request):
        nonlocal openrouter_calls
        openrouter_calls += 1
        return make_openrouter_response()

    gemini_client = httpx.AsyncClient(transport=httpx.MockTransport(gemini_handler))
    openrouter_client = httpx.AsyncClient(transport=httpx.MockTransport(openrouter_handler))

    gemini_prov = GeminiProvider(api_key="key1", client=gemini_client)
    openrouter_prov = OpenRouterProvider(api_key="key2", client=openrouter_client)

    manager = AIProviderManager(
        providers={"gemini": gemini_prov, "openrouter": openrouter_prov},
        priority_order=["gemini", "openrouter"],
        max_retries_per_provider=3,  # Even with max_retries=3, quota exhaustion must NOT retry
    )

    req = AIRequest(prompt="Classify feedback", response_schema=FeedbackCategoryModel)
    resp = await manager.generate(req)

    assert resp.provider == "openrouter"
    assert gemini_calls == 1  # Exactly 1 call, zero wasteful retries
    assert openrouter_calls == 1


@pytest.mark.anyio
async def test_openrouter_structured_output_compatibility_enforcement():
    """Verify OpenRouter filters out non-structured models when response_schema is present."""
    captured_payload = {}

    def openrouter_handler(req: httpx.Request):
        nonlocal captured_payload
        captured_payload = json.loads(req.read())
        return make_openrouter_response()

    client = httpx.AsyncClient(transport=httpx.MockTransport(openrouter_handler))
    prov = OpenRouterProvider(
        api_key="key",
        model="google/gemini-2.0-flash-001",
        fallback_models=["meta-llama/llama-3.3-70b-instruct", "unverified/arbitrary-model"],
        client=client,
    )

    req = AIRequest(prompt="Classify feedback", response_schema=FeedbackCategoryModel)
    await prov.generate(req)

    # Assert that only structured-output compatible models were routed in the payload
    assert "models" in captured_payload
    routed_models = captured_payload["models"]
    assert "google/gemini-2.0-flash-001" in routed_models
    assert "meta-llama/llama-3.3-70b-instruct" in routed_models
    assert "unverified/arbitrary-model" not in routed_models
