"""Google Gemini Embedding Provider Implementation.

Direct REST integration with Gemini Embedding 2 v1beta embedContent
and batchEmbedContents APIs using httpx with provider-specific error
classification and retry resilience.
"""

import asyncio
import datetime
from email.utils import parsedate_to_datetime
import logging
import time
from typing import Any, Dict, List, Optional, Union
import httpx

from app.core.config import settings
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
from app.integrations.embeddings.schemas import (
    EmbeddingBatchRequest,
    EmbeddingBatchResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)

logger = logging.getLogger("embedding_provider.gemini")


def _parse_retry_after(response: Optional[httpx.Response]) -> Optional[float]:
    """Extract and parse 'Retry-After' header in seconds if present."""
    if response is None:
        return None
    val = response.headers.get("Retry-After") or response.headers.get("retry-after")
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(val)
        delta = (dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
        return max(0.0, delta)
    except Exception:
        return None


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """Google Gemini Embedding provider using REST v1beta."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    MAX_BATCH_SIZE = 100  # Gemini official limit for batchEmbedContents

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(
            name="gemini",
            default_model=model or settings.AI_EMBEDDING_MODEL or "gemini-embedding-2",
            default_dimensions=dimensions or settings.AI_EMBEDDING_DIMENSIONS or 768,
            timeout_seconds=timeout_seconds or settings.AI_EMBEDDING_TIMEOUT or 30.0,
            max_retries=max_retries if max_retries is not None else settings.AI_EMBEDDING_MAX_RETRIES,
        )
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self._client = client

    @property
    def is_configured(self) -> bool:
        """Return True if Gemini API key is configured."""
        return bool(self.api_key and self.api_key.strip())

    def _get_clean_model_and_resource(self) -> tuple[str, str]:
        """Return (clean_model_name, resource_model_name) without duplicate 'models/' prefix."""
        clean = self.default_model.strip()
        if clean.startswith("models/"):
            clean = clean[len("models/") :]
        return clean, f"models/{clean}"

    def map_http_error(self, e: httpx.HTTPStatusError) -> EmbeddingError:
        """Provider-specific mapping of Gemini HTTP error payloads.

        Interprets Google RPC status, error details, and reason codes to accurately
        distinguish quota exhaustion from transient rate limiting and invalid credentials.
        """
        status = e.response.status_code
        retry_after = _parse_retry_after(e.response)

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

        reasons: List[str] = []
        if isinstance(details, list):
            for d in details:
                if isinstance(d, dict) and "reason" in d:
                    reasons.append(str(d["reason"]).upper())

        # 429 RESOURCE_EXHAUSTED: Quota Exhausted vs Transient Rate Limit
        if status == 429 or rpc_status == "RESOURCE_EXHAUSTED":
            is_quota_exhausted = (
                "QUOTA_EXCEEDED" in reasons
                or "quota exceeded" in lower_msg
                or "daily" in lower_msg
            )
            if is_quota_exhausted:
                return EmbeddingQuotaExhaustedError(
                    message=f"Gemini quota exhausted: {err_msg}",
                    provider=self.name,
                    status_code=status,
                    retry_after=retry_after,
                )
            return EmbeddingRateLimitError(
                message=f"Gemini rate limit exceeded: {err_msg}",
                provider=self.name,
                status_code=status,
                retry_after=retry_after,
            )

        # 401 / 403 Authentication / Authorization
        if status in (401, 403) or rpc_status == "PERMISSION_DENIED":
            return EmbeddingAuthError(
                message=f"Gemini authentication failed: {err_msg}",
                provider=self.name,
                status_code=status,
            )

        # 400 INVALID_ARGUMENT: Check for API Key format errors vs request errors
        if status == 400 or rpc_status == "INVALID_ARGUMENT":
            if "api key" in lower_msg or "API_KEY_INVALID" in reasons:
                return EmbeddingAuthError(
                    message=f"Gemini invalid API key: {err_msg}",
                    provider=self.name,
                    status_code=status,
                )
            return EmbeddingInvalidRequestError(
                message=f"Gemini invalid request: {err_msg}",
                provider=self.name,
                status_code=status,
            )

        # 5xx Service Unavailable / Internal Server Error
        if status >= 500:
            return EmbeddingUnavailableError(
                message=f"Gemini unavailable ({status}): {err_msg}",
                provider=self.name,
                status_code=status,
                retry_after=retry_after,
            )

        return EmbeddingError(
            message=f"Gemini HTTP {status}: {err_msg}",
            provider=self.name,
            status_code=status,
            retry_after=retry_after,
            is_transient=False,
        )

    async def _post_with_retry(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        item_count: int,
        target_dims: int,
    ) -> httpx.Response:
        """Execute HTTP POST with bounded retries and exponential backoff."""
        clean_model, _ = self._get_clean_model_and_resource()
        last_error: Optional[EmbeddingError] = None

        for attempt in range(self.max_retries + 1):
            start_attempt = time.perf_counter()
            try:
                if self._client is not None:
                    response = await self._client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    return response
                else:
                    async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                        response = await client.post(url, json=payload, headers=headers)
                        response.raise_for_status()
                        return response
            except asyncio.CancelledError:
                logger.info(
                    "Embedding request cancelled for %s/%s (items=%d)",
                    self.name,
                    clean_model,
                    item_count,
                )
                raise
            except httpx.TimeoutException as te:
                last_error = EmbeddingTimeoutError(
                    message=f"Gemini request timed out after {self.timeout_seconds}s: {str(te)}",
                    provider=self.name,
                )
            except httpx.HTTPStatusError as hse:
                last_error = self.map_http_error(hse)
            except httpx.RequestError as re:
                last_error = EmbeddingUnavailableError(
                    message=f"Gemini connection error: {str(re)}",
                    provider=self.name,
                )

            # Check retry eligibility
            if not last_error.is_transient or attempt >= self.max_retries:
                logger.warning(
                    "Embedding request failed permanently for %s/%s (items=%d, dims=%d, retry=%d/%d, error_category=%s): %s",
                    self.name,
                    clean_model,
                    item_count,
                    target_dims,
                    attempt,
                    self.max_retries,
                    type(last_error).__name__,
                    last_error.message,
                )
                raise last_error

            delay = self.calculate_backoff(attempt, last_error.retry_after)
            logger.info(
                "Embedding transient error for %s/%s (attempt %d/%d, sleeping %.2fs, error_category=%s)",
                self.name,
                clean_model,
                attempt + 1,
                self.max_retries,
                delay,
                type(last_error).__name__,
            )
            await asyncio.sleep(delay)

        # Fallback if loop ends unexpectedly
        if last_error:
            raise last_error
        raise EmbeddingUnavailableError("Request failed without response", provider=self.name)

    async def embed_text(
        self,
        text: Union[str, EmbeddingRequest],
        dimensions: Optional[int] = None,
    ) -> EmbeddingResponse:
        """Generate an embedding for a single text string."""
        if not self.is_configured:
            raise EmbeddingConfigurationError(
                "Gemini API key is not configured for embedding",
                provider=self.name,
            )

        if isinstance(text, EmbeddingRequest):
            raw_text = text.text
            requested_dims = text.dimensions or dimensions
        else:
            raw_text = text
            requested_dims = dimensions

        validated_text = self.validate_text(raw_text)
        target_dims = self.validate_dimensions(requested_dims)
        clean_model, resource_model = self._get_clean_model_and_resource()

        url = f"{self.BASE_URL}/models/{clean_model}:embedContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        payload: Dict[str, Any] = {
            "model": resource_model,
            "content": {
                "parts": [{"text": validated_text}]
            },
            "embedContentConfig": {
                "outputDimensionality": target_dims,
            },
        }

        start_time = time.perf_counter()
        response = await self._post_with_retry(
            url=url,
            payload=payload,
            headers=headers,
            item_count=1,
            target_dims=target_dims,
        )
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        try:
            body = response.json()
        except Exception as e:
            raise EmbeddingValidationError(
                f"Failed to parse JSON response: {str(e)}",
                provider=self.name,
            ) from e

        if not isinstance(body, dict) or "embedding" not in body or not isinstance(body["embedding"], dict):
            raise EmbeddingValidationError(
                "Malformed response from Gemini: missing 'embedding' object",
                provider=self.name,
            )

        raw_values = body["embedding"].get("values")
        if raw_values is None:
            raise EmbeddingValidationError(
                "Malformed response from Gemini: missing 'values' in embedding",
                provider=self.name,
            )

        vector = self.validate_vector(raw_values, target_dims)

        logger.info(
            "Generated 1 embedding using %s/%s (dims=%d, latency=%.2fms)",
            self.name,
            clean_model,
            target_dims,
            latency_ms,
        )

        return EmbeddingResponse(
            vector=vector,
            dimensions=target_dims,
            provider=self.name,
            model=clean_model,
            latency_ms=latency_ms,
        )

    async def embed_batch(
        self,
        texts: Union[List[str], EmbeddingBatchRequest],
        dimensions: Optional[int] = None,
    ) -> EmbeddingBatchResponse:
        """Generate embeddings for multiple texts using batchEmbedContents."""
        if not self.is_configured:
            raise EmbeddingConfigurationError(
                "Gemini API key is not configured for embedding",
                provider=self.name,
            )

        if isinstance(texts, EmbeddingBatchRequest):
            raw_texts = texts.texts
            requested_dims = texts.dimensions or dimensions
        else:
            raw_texts = texts
            requested_dims = dimensions

        validated_texts = self.validate_batch_texts(raw_texts)
        target_dims = self.validate_dimensions(requested_dims)
        clean_model, resource_model = self._get_clean_model_and_resource()

        url = f"{self.BASE_URL}/models/{clean_model}:batchEmbedContents"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        # Chunk inputs to respect official MAX_BATCH_SIZE (100)
        chunks = [
            validated_texts[i : i + self.MAX_BATCH_SIZE]
            for i in range(0, len(validated_texts), self.MAX_BATCH_SIZE)
        ]

        all_vectors: List[List[float]] = []
        start_time = time.perf_counter()

        for chunk_idx, chunk in enumerate(chunks):
            requests_payload = [
                {
                    "model": resource_model,
                    "content": {
                        "parts": [{"text": item}]
                    },
                    "embedContentConfig": {
                        "outputDimensionality": target_dims,
                    },
                }
                for item in chunk
            ]
            payload = {"requests": requests_payload}

            response = await self._post_with_retry(
                url=url,
                payload=payload,
                headers=headers,
                item_count=len(chunk),
                target_dims=target_dims,
            )

            try:
                body = response.json()
            except Exception as e:
                raise EmbeddingValidationError(
                    f"Failed to parse JSON response for batch chunk {chunk_idx}: {str(e)}",
                    provider=self.name,
                ) from e

            if not isinstance(body, dict) or "embeddings" not in body or not isinstance(body["embeddings"], list):
                raise EmbeddingValidationError(
                    f"Malformed response from Gemini in chunk {chunk_idx}: missing 'embeddings' array",
                    provider=self.name,
                )

            raw_embeddings = body["embeddings"]
            if len(raw_embeddings) != len(chunk):
                raise EmbeddingValidationError(
                    f"Gemini returned {len(raw_embeddings)} embeddings for chunk {chunk_idx} of size {len(chunk)}",
                    provider=self.name,
                )

            for item_idx, emb_item in enumerate(raw_embeddings):
                if not isinstance(emb_item, dict) or "values" not in emb_item:
                    raise EmbeddingValidationError(
                        f"Malformed embedding item at index {item_idx} in chunk {chunk_idx}: missing 'values'",
                        provider=self.name,
                    )
                vec = self.validate_vector(emb_item["values"], target_dims)
                all_vectors.append(vec)

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        logger.info(
            "Generated %d embeddings using %s/%s (dims=%d, chunks=%d, latency=%.2fms)",
            len(all_vectors),
            self.name,
            clean_model,
            target_dims,
            len(chunks),
            latency_ms,
        )

        return EmbeddingBatchResponse(
            vectors=all_vectors,
            dimensions=target_dims,
            provider=self.name,
            model=clean_model,
            count=len(all_vectors),
            latency_ms=latency_ms,
        )
