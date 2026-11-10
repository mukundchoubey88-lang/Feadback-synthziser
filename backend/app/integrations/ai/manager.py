"""AI Provider Manager and Failover Orchestrator.

Manages multi-provider execution with circuit breaking, deterministic failover,
bounded transient retries with exponential backoff, and privacy-safe observability.
"""

import asyncio
import logging
import random
import time
from typing import Dict, List, Optional, Tuple

from app.core.config import settings
from app.integrations.ai.base import BaseAIProvider
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
from app.integrations.ai.groq import GroqProvider
from app.integrations.ai.openrouter import OpenRouterProvider
from app.integrations.ai.schemas import AIRequest, AIResponse

logger = logging.getLogger("ai_provider.manager")


class AIProviderManager:
    """Orchestrates AI requests across multiple providers with automatic failover."""

    def __init__(
        self,
        providers: Optional[Dict[str, BaseAIProvider]] = None,
        priority_order: Optional[List[str]] = None,
        fallback_enabled: Optional[bool] = None,
        circuit_breaker: Optional[AIProviderCircuitBreaker] = None,
        max_retries_per_provider: Optional[int] = None,
    ):
        self.circuit_breaker = circuit_breaker or AIProviderCircuitBreaker(
            default_cooldown_seconds=settings.AI_PROVIDER_COOLDOWN_SECONDS
        )
        self.priority_order = (
            priority_order
            if priority_order is not None
            else settings.ai_provider_priority_list
        )
        self.fallback_enabled = (
            fallback_enabled
            if fallback_enabled is not None
            else settings.AI_PROVIDER_FALLBACK_ENABLED
        )
        self.max_retries = (
            max_retries_per_provider
            if max_retries_per_provider is not None
            else settings.AI_PROVIDER_MAX_RETRIES
        )

        if providers is not None:
            self._providers = {k.lower(): v for k, v in providers.items()}
        else:
            self._providers = {
                "gemini": GeminiProvider(),
                "openrouter": OpenRouterProvider(),
                "grok": GrokProvider(),
                "groq": GroqProvider(),
            }

    def register_provider(self, provider: BaseAIProvider) -> None:
        """Register or override a provider implementation."""
        self._providers[provider.name.lower()] = provider

    def get_provider(self, name: str) -> Optional[BaseAIProvider]:
        """Retrieve a registered provider by name."""
        return self._providers.get(name.lower())

    def _get_candidate_providers(self) -> List[Tuple[str, BaseAIProvider]]:
        """Return candidate providers in priority order."""
        candidates: List[Tuple[str, BaseAIProvider]] = []
        for prov_name in self.priority_order:
            name_key = prov_name.lower()
            provider = self._providers.get(name_key)
            # Seamless fallback between grok and groq aliases
            if (not provider or not provider.is_configured) and name_key == "grok":
                alt_groq = self._providers.get("groq")
                if alt_groq and alt_groq.is_configured:
                    provider = alt_groq
            elif (not provider or not provider.is_configured) and name_key == "groq":
                alt_grok = self._providers.get("grok")
                if alt_grok and alt_grok.is_configured:
                    provider = alt_grok

            if provider:
                candidates.append((name_key, provider))
        return candidates

    def _calculate_backoff(
        self, attempt: int, retry_after: Optional[float] = None
    ) -> float:
        """Calculate wait time with exponential backoff and jitter."""
        if retry_after is not None and retry_after > 0:
            return retry_after
        base_backoff = min(8.0, 0.5 * (2**attempt))
        jitter = random.uniform(0.05, 0.25)
        return base_backoff + jitter

    async def generate(self, request: AIRequest) -> AIResponse:
        """Execute request with automatic retry, circuit breaker checks, and failover.

        Privacy guarantee: Prompts and raw customer feedback are NEVER logged.
        """
        candidates = self._get_candidate_providers()

        # Check if at least one candidate is configured
        configured_candidates = [
            (name, prov) for name, prov in candidates if prov.is_configured
        ]
        if not configured_candidates:
            raise AIProviderAuthError(
                message="No AI providers are configured with valid API keys",
                provider="none",
                status_code=401,
            )

        failures: List[Tuple[str, Exception]] = []
        fallback_occurred = False
        last_failure_reason: Optional[str] = None

        for prov_idx, (prov_name, provider) in enumerate(candidates):
            # Check configuration
            if not provider.is_configured:
                logger.info(
                    "Skipping AI provider '%s': not configured with API credentials (cid=%s)",
                    prov_name,
                    request.correlation_id,
                )
                continue

            # Check circuit breaker availability
            if not self.circuit_breaker.is_available(prov_name):
                logger.warning(
                    "Skipping AI provider '%s': currently in cooldown circuit breaker (cid=%s)",
                    prov_name,
                    request.correlation_id,
                )
                failures.append(
                    (
                        prov_name,
                        AIProviderUnavailableError(
                            f"Provider '{prov_name}' in circuit breaker cooldown",
                            provider=prov_name,
                        ),
                    )
                )
                fallback_occurred = True
                continue

            # Provider is eligible; attempt generation with bounded retries
            attempt = 0
            while attempt <= self.max_retries:
                attempt += 1
                try:
                    response = await provider.generate(request)

                    # Priority 2: Guarantee manager never returns unvalidated output when schema was requested
                    if request.response_schema is not None and response.structured_data is None:
                        raise AIProviderValidationError(
                            message="Provider returned unvalidated structured data for requested schema",
                            provider=prov_name,
                            raw_output=response.content[:500],
                        )

                    # Successful response: record health and log safe observability metrics
                    self.circuit_breaker.record_success(prov_name)
                    logger.info(
                        "AI completion succeeded [provider=%s, model=%s, latency=%.1fms, "
                        "attempts=%d, prompt_tokens=%d, completion_tokens=%d, fallback=%s, cid=%s]",
                        response.provider,
                        response.model,
                        response.latency_ms,
                        attempt,
                        response.usage.prompt_tokens,
                        response.usage.completion_tokens,
                        fallback_occurred,
                        request.correlation_id,
                    )
                    return response

                except AIProviderInvalidRequestError as inv_err:
                    # Client-side 400 bad request must NOT retry and must NOT failover
                    logger.error(
                        "Permanent invalid request error on '%s': %s (cid=%s)",
                        prov_name,
                        inv_err.message,
                        request.correlation_id,
                    )
                    raise inv_err

                except AIProviderAuthError as auth_err:
                    # Authentication or key invalid: disable provider, fall over without retry
                    logger.warning(
                        "AI provider '%s' authentication failed: %s (cid=%s). Falling over.",
                        prov_name,
                        auth_err.message,
                        request.correlation_id,
                    )
                    self.circuit_breaker.disable_provider(
                        prov_name, f"Auth failure: {auth_err.message}"
                    )
                    failures.append((prov_name, auth_err))
                    last_failure_reason = f"Auth error ({auth_err.message})"
                    fallback_occurred = True
                    break

                except AIProviderQuotaExhaustedError as quota_err:
                    # Quota/credits exhausted: apply cooldown immediately and fall over
                    logger.warning(
                        "AI provider '%s' quota exhausted: %s (cid=%s). Falling over.",
                        prov_name,
                        quota_err.message,
                        request.correlation_id,
                    )
                    self.circuit_breaker.record_failure(
                        prov_name,
                        quota_err,
                        cooldown_seconds=settings.AI_PROVIDER_COOLDOWN_SECONDS,
                    )
                    failures.append((prov_name, quota_err))
                    last_failure_reason = "Quota exhausted"
                    fallback_occurred = True
                    break

                except AIProviderValidationError as val_err:
                    # Controlled validation recovery: allow at most 1 repair retry on current provider
                    if attempt == 1 and self.max_retries > 0:
                        logger.warning(
                            "Validation failure on '%s' (attempt 1): %s. Attempting 1 repair retry (cid=%s)",
                            prov_name,
                            val_err.message,
                            request.correlation_id,
                        )
                        continue
                    else:
                        logger.warning(
                            "Validation failure on '%s' exhausted repair attempts: %s (cid=%s). Falling over.",
                            prov_name,
                            val_err.message,
                            request.correlation_id,
                        )
                        self.circuit_breaker.record_failure(
                            prov_name,
                            val_err,
                            cooldown_seconds=settings.AI_PROVIDER_COOLDOWN_SECONDS,
                        )
                        failures.append((prov_name, val_err))
                        last_failure_reason = f"Validation failure: {val_err.message}"
                        fallback_occurred = True
                        break

                except (
                    AIProviderRateLimitError,
                    AIProviderTimeoutError,
                    AIProviderUnavailableError,
                ) as transient_err:
                    # Transient error: determine if we should retry or fail over
                    is_last_attempt = attempt > self.max_retries
                    if not is_last_attempt:
                        backoff = self._calculate_backoff(
                            attempt, transient_err.retry_after
                        )
                        logger.warning(
                            "Transient failure on '%s' (attempt %d/%d): %s. Retrying in %.2fs (cid=%s)",
                            prov_name,
                            attempt,
                            self.max_retries + 1,
                            transient_err.message,
                            backoff,
                            request.correlation_id,
                        )
                        await asyncio.sleep(backoff)
                        continue
                    else:
                        # Retries exhausted on this provider: put into cooldown and fail over
                        logger.warning(
                            "AI provider '%s' exhausted %d retries: %s (cid=%s). Falling over.",
                            prov_name,
                            attempt,
                            transient_err.message,
                            request.correlation_id,
                        )
                        self.circuit_breaker.record_failure(
                            prov_name,
                            transient_err,
                            cooldown_seconds=settings.AI_PROVIDER_COOLDOWN_SECONDS,
                        )
                        failures.append((prov_name, transient_err))
                        last_failure_reason = transient_err.message
                        fallback_occurred = True
                        break

                except Exception as unhandled_err:
                    logger.error(
                        "Unexpected error on AI provider '%s': %s (cid=%s). Falling over.",
                        prov_name,
                        str(unhandled_err),
                        request.correlation_id,
                    )
                    self.circuit_breaker.record_failure(prov_name, unhandled_err)
                    failures.append((prov_name, unhandled_err))
                    last_failure_reason = str(unhandled_err)
                    fallback_occurred = True
                    break

            # If fallback is explicitly disabled by configuration, do not attempt secondary providers
            if not self.fallback_enabled:
                logger.info("Provider fallback is disabled; halting failover chain")
                break

        # All eligible providers failed
        raise AllAIProvidersFailedError(
            message=f"All configured AI providers failed (last failure: {last_failure_reason})",
            failures=failures,
        )
