from fastapi import APIRouter
from app.core.config import settings
from app.schemas.health import HealthResponse, DependencyStatus

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Application Health Check",
    description="Returns API service availability and reports configuration state of external dependencies.",
)
async def get_health() -> HealthResponse:
    """Return structured health status of the API and its configured external dependencies.

    External dependencies are explicitly distinguished between 'not_configured' and 'not_checked'
    without making premature external network calls or falsely claiming connectivity.
    """
    # Evaluate Database configuration state
    if settings.DATABASE_URL:
        db_status = DependencyStatus(
            status="not_checked",
            details="DATABASE_URL configured; active connectivity verification deferred to Part 2",
        )
    else:
        db_status = DependencyStatus(
            status="not_configured",
            details="DATABASE_URL not configured in environment",
        )

    # Evaluate Gemini AI configuration state
    if settings.GEMINI_API_KEY:
        gemini_status = DependencyStatus(
            status="not_checked",
            details="GEMINI_API_KEY provided; operational client deferred to Part 4",
        )
    else:
        gemini_status = DependencyStatus(
            status="not_configured",
            details="GEMINI_API_KEY not configured in environment",
        )

    # Evaluate Hindsight Persistent Memory configuration state
    if settings.HINDSIGHT_API_KEY:
        hindsight_status = DependencyStatus(
            status="not_checked",
            details="HINDSIGHT_API_KEY provided; operational client deferred to Part 9",
        )
    else:
        hindsight_status = DependencyStatus(
            status="not_configured",
            details="HINDSIGHT_API_KEY not configured in environment",
        )

    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        version="1.0.0",
        environment=settings.APP_ENV,
        dependencies={
            "database": db_status,
            "gemini": gemini_status,
            "hindsight": hindsight_status,
        },
    )
