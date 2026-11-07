"""AI Provider Schemas.

Defines provider-agnostic request, response, and token usage schemas for
the multi-provider AI integration.
"""

from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field


class AIRequest(BaseModel):
    """Normalized request payload passed to any AI provider."""

    prompt: str = Field(..., description="User prompt or task payload")
    system_instruction: Optional[str] = Field(
        default=None, description="System persona or instruction"
    )
    response_schema: Optional[Type[BaseModel]] = Field(
        default=None,
        description="Optional Pydantic model for strict structured JSON output",
    )
    temperature: float = Field(
        default=0.2, ge=0.0, le=2.0, description="Sampling temperature"
    )
    max_output_tokens: Optional[int] = Field(
        default=None, gt=0, description="Maximum completion tokens"
    )
    correlation_id: Optional[str] = Field(
        default=None, description="Tracing/correlation identifier for request logs"
    )

    model_config = {
        "arbitrary_types_allowed": True,
    }


class AIUsage(BaseModel):
    """Token usage and estimated cost metadata."""

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cost_usd: Optional[float] = Field(
        default=None, ge=0.0, description="Estimated request cost in USD"
    )


class AIResponse(BaseModel):
    """Normalized response payload returned by any AI provider."""

    content: str = Field(..., description="Raw string content returned by provider")
    raw_json: Optional[Dict[str, Any]] = Field(
        default=None, description="Parsed JSON dictionary if JSON output was requested"
    )
    structured_data: Optional[Any] = Field(
        default=None,
        description="Validated Pydantic model instance if response_schema was requested",
    )
    provider: str = Field(..., description="Name of the responding provider")
    model: str = Field(..., description="Specific model that generated the completion")
    latency_ms: float = Field(..., ge=0.0, description="Request duration in milliseconds")
    usage: AIUsage = Field(default_factory=AIUsage)
    correlation_id: Optional[str] = Field(
        default=None, description="Tracing/correlation identifier"
    )

    model_config = {
        "arbitrary_types_allowed": True,
    }
