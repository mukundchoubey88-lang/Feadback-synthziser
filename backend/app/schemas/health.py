from typing import Dict, Optional
from pydantic import BaseModel, Field


class DependencyStatus(BaseModel):
    """Status description for external dependencies."""
    status: str = Field(
        ...,
        description="Dependency status: 'not_configured', 'not_checked', 'connected', or 'unreachable'",
        examples=["not_configured", "not_checked"],
    )
    details: Optional[str] = Field(
        None,
        description="Additional context regarding dependency configuration",
    )


class HealthResponse(BaseModel):
    """Structured health response distinguishing API availability from external dependencies."""
    status: str = Field(..., examples=["healthy"])
    app_name: str = Field(..., examples=["Feedback Intelligence API"])
    version: str = Field(..., examples=["1.0.0"])
    environment: str = Field(..., examples=["development"])
    dependencies: Dict[str, DependencyStatus] = Field(
        ...,
        description="External dependency availability and configuration states",
    )


class RootInfoResponse(BaseModel):
    """Basic root application information."""
    name: str = Field(..., examples=["Feedback Intelligence API"])
    version: str = Field(..., examples=["1.0.0"])
    environment: str = Field(..., examples=["development"])
    docs_url: str = Field(..., examples=["/docs"])
    status: str = Field(..., examples=["online"])
