"""Multi-Provider AI Integration Package.

Provides Google Gemini, OpenRouter, and xAI Grok provider implementations
with automated circuit-broken failover management.
"""

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
from app.integrations.ai.manager import AIProviderManager
from app.integrations.ai.openrouter import OpenRouterProvider
from app.integrations.ai.schemas import AIRequest, AIResponse, AIUsage

__all__ = [
    "AIProviderCircuitBreaker",
    "AIProviderError",
    "AIProviderAuthError",
    "AIProviderInvalidRequestError",
    "AIProviderQuotaExhaustedError",
    "AIProviderRateLimitError",
    "AIProviderTimeoutError",
    "AIProviderUnavailableError",
    "AIProviderValidationError",
    "AllAIProvidersFailedError",
    "AIRequest",
    "AIResponse",
    "AIUsage",
    "BaseAIProvider",
    "GeminiProvider",
    "GrokProvider",
    "OpenRouterProvider",
    "AIProviderManager",
]
