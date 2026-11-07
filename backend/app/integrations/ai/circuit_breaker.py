"""In-Memory Circuit Breaker and Cooldown Tracker for AI Providers.

Tracks provider availability, rate-limiting backoffs, cooldown states,
and safe diagnostic summaries.

NOTE ON STATE SCOPE:
This circuit breaker maintains process-local in-memory state. State is tracked
per worker process and is not shared across distributed workers or multi-node
clusters (which would require an external coordinator such as Redis). For this MVP,
process-local tracking prevents external infrastructure coupling while providing
strict protection against thundering-herd retries and provider stampedes.
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger("ai_provider_circuit_breaker")


@dataclass
class ProviderHealth:
    """State record for a single AI provider."""

    failure_count: int = 0
    last_failure_time: Optional[float] = None
    cooldown_until: Optional[float] = None
    last_error_type: Optional[str] = None
    is_disabled: bool = False
    disabled_reason: Optional[str] = None
    is_probing: bool = False  # True when executing a probationary half-open request


class AIProviderCircuitBreaker:
    """Thread-safe / async-safe in-memory process-local circuit breaker for AI providers."""

    def __init__(self, default_cooldown_seconds: float = 60.0):
        self.default_cooldown_seconds = default_cooldown_seconds
        self._providers: Dict[str, ProviderHealth] = {}
        self._lock = threading.Lock()

    def _get_health(self, provider: str) -> ProviderHealth:
        provider_key = provider.lower()
        if provider_key not in self._providers:
            self._providers[provider_key] = ProviderHealth()
        return self._providers[provider_key]

    def is_available(self, provider: str) -> bool:
        """Check if a provider is currently available to accept requests.

        Implements half-open probationary behavior: when cooldown has expired, exactly
        one request is permitted to probe the provider. Cooldown is extended by a short
        probationary window (e.g. 10s) to prevent concurrent requests from stampeding
        the recovering provider before the probe completes.
        """
        with self._lock:
            health = self._get_health(provider)
            if health.is_disabled:
                return False

            now = time.time()
            if health.cooldown_until is not None:
                if now < health.cooldown_until:
                    # Still in cooldown or currently undergoing a probationary probe
                    return False

                # Cooldown expired: transition to half-open probationary state.
                # Extend cooldown_until by a probationary window so concurrent requests
                # do not bypass cooldown while this probe executes.
                probe_window = min(10.0, self.default_cooldown_seconds)
                health.cooldown_until = now + probe_window
                health.is_probing = True
                logger.info(
                    "AI Provider '%s' entered half-open probationary probe (window=%.1fs)",
                    provider,
                    probe_window,
                )
                return True

            return True

    def record_success(self, provider: str) -> None:
        """Record a successful response, resetting consecutive failure metrics."""
        with self._lock:
            health = self._get_health(provider)
            health.failure_count = 0
            health.cooldown_until = None
            health.last_error_type = None
            health.is_probing = False

    def record_failure(
        self,
        provider: str,
        error: Optional[Exception] = None,
        cooldown_seconds: Optional[float] = None,
    ) -> None:
        """Record a provider failure and apply cooldown."""
        with self._lock:
            health = self._get_health(provider)
            health.failure_count += 1
            health.is_probing = False
            now = time.time()
            health.last_failure_time = now

            # Determine effective cooldown
            retry_after: Optional[float] = None
            if error is not None:
                health.last_error_type = type(error).__name__
                retry_after = getattr(error, "retry_after", None)

            effective_cooldown = cooldown_seconds or self.default_cooldown_seconds
            if retry_after is not None and retry_after > 0:
                effective_cooldown = max(effective_cooldown, retry_after)

            health.cooldown_until = now + effective_cooldown
            logger.warning(
                "AI Provider '%s' put into cooldown for %.1f seconds (failures: %d, reason: %s)",
                provider,
                effective_cooldown,
                health.failure_count,
                health.last_error_type,
            )

    def disable_provider(self, provider: str, reason: str) -> None:
        """Mark a provider permanently or configurationally disabled."""
        with self._lock:
            health = self._get_health(provider)
            health.is_disabled = True
            health.disabled_reason = reason
            health.is_probing = False
            logger.warning("AI Provider '%s' permanently disabled: %s", provider, reason)

    def reset(self) -> None:
        """Reset all circuit breaker tracking (used in testing)."""
        with self._lock:
            self._providers.clear()

    def get_status(self) -> Dict[str, Any]:
        """Return a safe diagnostic summary of all provider states."""
        with self._lock:
            now = time.time()
            summary: Dict[str, Any] = {}
            for prov, health in self._providers.items():
                in_cooldown = (
                    health.cooldown_until is not None and now < health.cooldown_until
                )
                remaining_cooldown = (
                    max(0.0, health.cooldown_until - now)
                    if in_cooldown and health.cooldown_until
                    else 0.0
                )
                summary[prov] = {
                    "available": not health.is_disabled and not in_cooldown,
                    "is_disabled": health.is_disabled,
                    "disabled_reason": health.disabled_reason,
                    "failure_count": health.failure_count,
                    "in_cooldown": in_cooldown,
                    "is_probing": health.is_probing,
                    "remaining_cooldown_seconds": round(remaining_cooldown, 2),
                    "last_error_type": health.last_error_type,
                }
            return summary
