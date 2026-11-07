"""Comprehensive unit and integration tests for the Text Embedding Providers.

Verifies BaseEmbeddingProvider, GeminiEmbeddingProvider, and MockEmbeddingProvider
against official Google Gemini REST API contracts, MRL dimension validation,
input validation, finite number checks, bounded retries, and privacy safeguards.
"""

import asyncio
import json
import math
from typing import Any, Dict, List
import httpx
import pytest

from app.integrations.embeddings.base import BaseEmbeddingProvider
from app.integrations.embeddings.exceptions import (
    EmbeddingAuthError,
    EmbeddingConfigurationError,
    EmbeddingError,
    EmbeddingInvalidRequestError,
    EmbeddingQuotaExhaustedError,
    EmbeddingRateLimitError,
    EmbeddingTimeoutError,
    EmbeddingUnavailableError,
    EmbeddingValidationError,
)
from app.integrations.embeddings.gemini import GeminiEmbeddingProvider
from app.integrations.embeddings.mock import MockEmbeddingProvider
from app.integrations.embeddings.schemas import (
    EmbeddingBatchRequest,
    EmbeddingRequest,
)


def make_vector(dim: int = 768, val: float = 0.05) -> List[float]:
    """Generate a valid finite float vector of given dimension."""
    norm = math.sqrt(dim * (val**2))
    unit_val = val / norm if norm > 0 else val
    return [unit_val] * dim


# ---------------------------------------------------------------------------
# GeminiEmbeddingProvider Unit Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_successful_single_embedding():
    """Verify single embedding generation with gemini-embedding-2."""
    captured_requests: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            status_code=200,
            json={"embedding": {"values": make_vector(768, 0.1)}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = GeminiEmbeddingProvider(
        api_key="test-gemini-key",
        model="gemini-embedding-2",
        dimensions=768,
        client=client,
    )

    response = await provider.embed_text("Checkout button fails on iOS 17.")

    assert response.provider == "gemini"
    assert response.model == "gemini-embedding-2"
    assert response.dimensions == 768
    assert len(response.vector) == 768
    assert response.latency_ms >= 0.0

    # Verify wire contract
    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req.method == "POST"
    assert str(req.url) == "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent"
    assert req.headers.get("x-goog-api-key") == "test-gemini-key"
    assert "key=" not in str(req.url)  # No secret in URL

    body = json.loads(req.content.decode("utf-8"))
    assert body["model"] == "models/gemini-embedding-2"
    assert "outputDimensionality" not in body  # Top-level is deprecated
    assert body.get("embedContentConfig", {}).get("outputDimensionality") == 768
    assert body["content"]["parts"][0]["text"] == "Checkout button fails on iOS 17."
    assert "taskType" not in body  # Must NOT send taskType to gemini-embedding-2
    assert "task_type" not in body
    assert "taskType" not in body.get("embedContentConfig", {})
    assert "task_type" not in body.get("embedContentConfig", {})


@pytest.mark.anyio
async def test_successful_multiple_independent_embeddings():
    """Verify multiple independent embeddings using batchEmbedContents."""
    captured_requests: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            status_code=200,
            json={
                "embeddings": [
                    {"values": make_vector(768, 0.1)},
                    {"values": make_vector(768, 0.2)},
                    {"values": make_vector(768, 0.3)},
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = GeminiEmbeddingProvider(
        api_key="test-gemini-key",
        model="gemini-embedding-2",
        dimensions=768,
        client=client,
    )

    texts = [
        "First customer complaint",
        "Second customer suggestion",
        "Third customer bug report",
    ]
    response = await provider.embed_batch(texts)

    assert response.provider == "gemini"
    assert response.model == "gemini-embedding-2"
    assert response.count == 3
    assert len(response.vectors) == 3
    assert all(len(v) == 768 for v in response.vectors)

    req = captured_requests[0]
    assert str(req.url) == "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:batchEmbedContents"
    body = json.loads(req.content.decode("utf-8"))
    assert len(body["requests"]) == 3
    assert body["requests"][0]["content"]["parts"][0]["text"] == texts[0]
    assert body["requests"][1]["content"]["parts"][0]["text"] == texts[1]
    assert body["requests"][2]["content"]["parts"][0]["text"] == texts[2]
    for r in body["requests"]:
        assert "outputDimensionality" not in r  # Deprecated top-level is absent
        assert r.get("embedContentConfig", {}).get("outputDimensionality") == 768
        assert "taskType" not in r
        assert "task_type" not in r
        assert "taskType" not in r.get("embedContentConfig", {})
        assert "task_type" not in r.get("embedContentConfig", {})


@pytest.mark.anyio
async def test_batch_chunking_over_100_items():
    """Verify large batches are chunked into groups <= 100 adhering to Gemini limits."""
    captured_requests: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        body = json.loads(request.content.decode("utf-8"))
        count = len(body["requests"])
        return httpx.Response(
            status_code=200,
            json={"embeddings": [{"values": make_vector(768, 0.01)} for _ in range(count)]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = GeminiEmbeddingProvider(
        api_key="test-gemini-key",
        model="gemini-embedding-2",
        dimensions=768,
        client=client,
    )

    total_items = 105
    texts = [f"Feedback item {i}" for i in range(total_items)]
    response = await provider.embed_batch(texts)

    assert response.count == 105
    assert len(response.vectors) == 105
    assert len(captured_requests) == 2  # 100 + 5

    req1_body = json.loads(captured_requests[0].content.decode("utf-8"))
    req2_body = json.loads(captured_requests[1].content.decode("utf-8"))
    assert len(req1_body["requests"]) == 100
    assert len(req2_body["requests"]) == 5


@pytest.mark.anyio
async def test_configurable_output_dimensions():
    """Verify requested dimensions override (MRL) works as expected."""
    captured_requests: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            status_code=200,
            json={"embedding": {"values": make_vector(256, 0.2)}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = GeminiEmbeddingProvider(
        api_key="test-gemini-key",
        dimensions=768,
        client=client,
    )

    response = await provider.embed_text("Test feedback", dimensions=256)
    assert response.dimensions == 256
    assert len(response.vector) == 256

    body = json.loads(captured_requests[0].content.decode("utf-8"))
    assert "outputDimensionality" not in body  # Deprecated top-level is absent
    assert body.get("embedContentConfig", {}).get("outputDimensionality") == 256


@pytest.mark.anyio
async def test_invalid_or_empty_input():
    """Verify empty or non-string inputs are rejected before network calls."""
    provider = GeminiEmbeddingProvider(api_key="test-gemini-key")

    with pytest.raises(EmbeddingInvalidRequestError, match="cannot be empty or whitespace-only"):
        await provider.embed_text("")

    with pytest.raises(EmbeddingInvalidRequestError, match="cannot be empty or whitespace-only"):
        await provider.embed_text("    \n\t   ")

    with pytest.raises(EmbeddingInvalidRequestError, match="must be a string"):
        await provider.embed_text(12345)  # type: ignore

    with pytest.raises(EmbeddingInvalidRequestError, match="cannot be empty"):
        await provider.embed_batch([])

    with pytest.raises(EmbeddingInvalidRequestError, match="must be a string"):
        await provider.embed_batch(["valid", None])  # type: ignore

    with pytest.raises(EmbeddingInvalidRequestError, match="cannot be empty or whitespace-only"):
        await provider.embed_batch(["valid", "   "])

    with pytest.raises(EmbeddingInvalidRequestError, match="must be a positive integer"):
        await provider.embed_text("Valid text", dimensions=-1)


@pytest.mark.anyio
async def test_missing_api_key_configuration_error():
    """Verify missing API key raises EmbeddingConfigurationError."""
    provider = GeminiEmbeddingProvider(api_key="")
    assert not provider.is_configured

    with pytest.raises(EmbeddingConfigurationError, match="not configured"):
        await provider.embed_text("Valid text")

    with pytest.raises(EmbeddingConfigurationError, match="not configured"):
        await provider.embed_batch(["Valid text"])


@pytest.mark.anyio
async def test_authentication_failure_handling():
    """Verify HTTP 401/403 triggers non-transient EmbeddingAuthError without retry."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            status_code=401,
            json={"error": {"code": 401, "message": "API key not valid", "status": "UNAUTHENTICATED"}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = GeminiEmbeddingProvider(
        api_key="invalid-key",
        max_retries=2,
        client=client,
    )

    with pytest.raises(EmbeddingAuthError) as exc_info:
        await provider.embed_text("Valid text")

    assert call_count == 1  # Did not retry
    assert exc_info.value.status_code == 401
    assert not exc_info.value.is_transient


@pytest.mark.anyio
async def test_rate_limit_transient_retry():
    """Verify transient 429 rate limit retries and succeeds."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                status_code=429,
                headers={"Retry-After": "0.01"},
                json={"error": {"code": 429, "message": "Rate limit exceeded", "status": "RESOURCE_EXHAUSTED"}},
            )
        return httpx.Response(
            status_code=200,
            json={"embedding": {"values": make_vector(768, 0.1)}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = GeminiEmbeddingProvider(
        api_key="valid-key",
        max_retries=2,
        client=client,
    )

    response = await provider.embed_text("Valid text")
    assert call_count == 2
    assert response.dimensions == 768


@pytest.mark.anyio
async def test_quota_exhausted_no_retry():
    """Verify permanent quota exhaustion raises non-transient EmbeddingQuotaExhaustedError."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            status_code=429,
            json={
                "error": {
                    "code": 429,
                    "message": "Resource has been exhausted (e.g. check quota)",
                    "status": "RESOURCE_EXHAUSTED",
                    "details": [{"reason": "QUOTA_EXCEEDED"}],
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = GeminiEmbeddingProvider(
        api_key="valid-key",
        max_retries=2,
        client=client,
    )

    with pytest.raises(EmbeddingQuotaExhaustedError) as exc_info:
        await provider.embed_text("Valid text")

    assert call_count == 1  # Does not retry quota exhaustion
    assert not exc_info.value.is_transient


@pytest.mark.anyio
async def test_temporary_server_error_and_retry_exhaustion():
    """Verify 503 server error retries up to max_retries then raises EmbeddingUnavailableError."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            status_code=503,
            json={"error": {"code": 503, "message": "Backend unavailable", "status": "UNAVAILABLE"}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = GeminiEmbeddingProvider(
        api_key="valid-key",
        timeout_seconds=2.0,
        max_retries=2,
        client=client,
    )

    with pytest.raises(EmbeddingUnavailableError) as exc_info:
        await provider.embed_text("Valid text")

    # 1 initial attempt + 2 retries = 3 attempts total
    assert call_count == 3
    assert exc_info.value.status_code == 503
    assert exc_info.value.is_transient


@pytest.mark.anyio
async def test_timeout_handling():
    """Verify request timeout raises EmbeddingTimeoutError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Connection timed out")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = GeminiEmbeddingProvider(
        api_key="valid-key",
        timeout_seconds=1.0,
        max_retries=1,
        client=client,
    )

    with pytest.raises(EmbeddingTimeoutError):
        await provider.embed_text("Valid text")


@pytest.mark.anyio
async def test_invalid_vector_dimensions_error():
    """Verify provider response with wrong vector dimensionality raises EmbeddingValidationError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={"embedding": {"values": make_vector(512, 0.1)}},  # Returned 512, expected 768
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = GeminiEmbeddingProvider(
        api_key="valid-key",
        dimensions=768,
        client=client,
    )

    with pytest.raises(EmbeddingValidationError, match="Expected embedding dimension 768, got 512"):
        await provider.embed_text("Valid text")


@pytest.mark.anyio
async def test_nan_or_infinite_vector_values_error():
    """Verify NaN or Infinite float values raise EmbeddingValidationError."""
    # Test NaN using raw encoded json content allowing NaN
    nan_vector = make_vector(768, 0.1)
    nan_vector[10] = float("nan")
    raw_nan_content = json.dumps({"embedding": {"values": nan_vector}}, allow_nan=True).encode("utf-8")

    def nan_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            content=raw_nan_content,
            headers={"Content-Type": "application/json"},
        )

    client_nan = httpx.AsyncClient(transport=httpx.MockTransport(nan_handler))
    provider_nan = GeminiEmbeddingProvider(
        api_key="valid-key",
        dimensions=768,
        client=client_nan,
    )

    with pytest.raises(EmbeddingValidationError, match="non-finite value"):
        await provider_nan.embed_text("Valid text")

    # Test +Infinity
    inf_vector = make_vector(768, 0.1)
    inf_vector[20] = float("inf")
    raw_inf_content = json.dumps({"embedding": {"values": inf_vector}}, allow_nan=True).encode("utf-8")

    def inf_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            content=raw_inf_content,
            headers={"Content-Type": "application/json"},
        )

    client_inf = httpx.AsyncClient(transport=httpx.MockTransport(inf_handler))
    provider_inf = GeminiEmbeddingProvider(
        api_key="valid-key",
        dimensions=768,
        client=client_inf,
    )

    with pytest.raises(EmbeddingValidationError, match="non-finite value"):
        await provider_inf.embed_text("Valid text")


@pytest.mark.anyio
async def test_malformed_response_payload():
    """Verify missing fields in provider response raise EmbeddingValidationError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json={"unexpected": "structure"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = GeminiEmbeddingProvider(
        api_key="valid-key",
        client=client,
    )

    with pytest.raises(EmbeddingValidationError, match="missing 'embedding' object"):
        await provider.embed_text("Valid text")


@pytest.mark.anyio
async def test_secret_redaction_and_privacy():
    """Verify secrets and customer feedback text are never leaked in error representations."""
    captured_requests: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(status_code=401, json={"error": {"message": "Invalid API key"}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = GeminiEmbeddingProvider(
        api_key="SUPER_SECRET_KEY_12345",
        client=client,
    )

    with pytest.raises(EmbeddingAuthError) as exc_info:
        await provider.embed_text("Customer SSN: 000-11-2222")

    err_str = str(exc_info.value)
    assert "SUPER_SECRET_KEY_12345" not in err_str
    assert "Customer SSN" not in err_str

    req = captured_requests[0]
    assert "SUPER_SECRET_KEY_12345" not in str(req.url)


@pytest.mark.anyio
async def test_cancellation_behaviour():
    """Verify cancellation cleanly propagates asyncio.CancelledError without retry."""
    async def cancelling_task():
        async def hang_forever(request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(10.0)
            return httpx.Response(status_code=200, json={})

        client = httpx.AsyncClient(transport=httpx.MockTransport(hang_forever))
        provider = GeminiEmbeddingProvider(
            api_key="valid-key",
            timeout_seconds=30.0,
            client=client,
        )
        await provider.embed_text("Valid text")

    task = asyncio.create_task(cancelling_task())
    await asyncio.sleep(0.02)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


# ---------------------------------------------------------------------------
# MockEmbeddingProvider Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_mock_embedding_provider_deterministic():
    """Verify MockEmbeddingProvider generates deterministic, unit-normalized vectors."""
    provider = MockEmbeddingProvider(default_dimensions=768)

    res1 = await provider.embed_text("Same customer feedback text")
    res2 = await provider.embed_text("Same customer feedback text")
    res3 = await provider.embed_text("Different customer feedback text")

    assert res1.vector == res2.vector
    assert res1.vector != res3.vector
    assert len(res1.vector) == 768

    # Check unit norm
    norm1 = math.sqrt(sum(x * x for x in res1.vector))
    assert abs(norm1 - 1.0) < 1e-5


@pytest.mark.anyio
async def test_mock_embedding_provider_batch():
    """Verify MockEmbeddingProvider batch processing."""
    provider = MockEmbeddingProvider(default_dimensions=512)

    batch_res = await provider.embed_batch(
        ["Item one", "Item two", "Item three"],
        dimensions=512,
    )

    assert batch_res.count == 3
    assert len(batch_res.vectors) == 3
    assert all(len(v) == 512 for v in batch_res.vectors)
    assert batch_res.vectors[0] != batch_res.vectors[1]


@pytest.mark.anyio
async def test_mock_embedding_provider_simulated_errors():
    """Verify MockEmbeddingProvider can simulate transient failures and recovery."""
    provider = MockEmbeddingProvider(
        transient_failures_remaining=1,
        transient_error_factory=lambda: EmbeddingRateLimitError("Mock rate limit"),
    )

    # First call triggers the transient failure
    with pytest.raises(EmbeddingRateLimitError):
        await provider.embed_text("Item 1")

    # Second call succeeds
    res = await provider.embed_text("Item 1")
    assert res.dimensions == 768


@pytest.mark.anyio
async def test_embed_content_config_structure_and_deprecation_enforcement():
    """Verify that both single and batch requests strictly use embedContentConfig.outputDimensionality
    and contain no deprecated top-level outputDimensionality or taskType fields.
    """
    captured: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if "batchEmbedContents" in str(request.url):
            return httpx.Response(
                status_code=200,
                json={"embeddings": [{"values": make_vector(768, 0.05)}, {"values": make_vector(768, 0.05)}]},
            )
        return httpx.Response(
            status_code=200,
            json={"embedding": {"values": make_vector(768, 0.05)}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = GeminiEmbeddingProvider(
        api_key="test-key",
        model="gemini-embedding-2",
        dimensions=768,
        client=client,
    )

    # 1. Test single embed_text
    await provider.embed_text("Sample feedback")
    single_req = captured[0]
    single_body = json.loads(single_req.content.decode("utf-8"))

    # Assertions for single request:
    assert "outputDimensionality" not in single_body, "Top-level outputDimensionality is deprecated"
    assert "taskType" not in single_body
    assert "task_type" not in single_body
    assert "embedContentConfig" in single_body
    assert single_body["embedContentConfig"] == {"outputDimensionality": 768}

    # 2. Test batch embed_batch
    await provider.embed_batch(["Feedback 1", "Feedback 2"])
    batch_req = captured[1]
    batch_body = json.loads(batch_req.content.decode("utf-8"))

    # Assertions for batch request:
    assert "outputDimensionality" not in batch_body
    assert "requests" in batch_body
    assert len(batch_body["requests"]) == 2
    for item in batch_body["requests"]:
        assert "outputDimensionality" not in item, "Top-level outputDimensionality in batch item is deprecated"
        assert "taskType" not in item
        assert "task_type" not in item
        assert "embedContentConfig" in item
        assert item["embedContentConfig"] == {"outputDimensionality": 768}
