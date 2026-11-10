"""API routes for Historical Memory Intelligence (Part 10 - Hackathon Prototype).

Endpoints:
- POST /api/intelligence/ask: Unified natural-language intelligence endpoint combining
  PostgreSQL structured metrics, themes, release changelogs, and Hindsight reflections.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.integrations.ai.manager import AIProviderManager
from app.integrations.hindsight.client import HindsightClient
from app.schemas.intelligence import (
    HistoricalIntelligenceRequest,
    HistoricalIntelligenceResponse,
)
from app.services.historical_intelligence_service import HistoricalIntelligenceService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_hindsight_client() -> HindsightClient:
    """Dependency provider for Hindsight REST API client."""
    return HindsightClient()


def get_ai_manager() -> Optional[AIProviderManager]:
    """Dependency provider for multi-provider AI failover manager."""
    try:
        return AIProviderManager()
    except Exception as exc:
        logger.debug("AIProviderManager could not be initialized (%s); fallback synthesizer will be used.", exc)
        return None


@router.post(
    "/ask",
    response_model=HistoricalIntelligenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask natural-language intelligence question",
    description=(
        "Synthesizes PostgreSQL structured analytics, theme context, release changelogs, "
        "and Hindsight historical memories into a grounded, evidence-backed answer."
    ),
)
async def ask_intelligence(
    payload: HistoricalIntelligenceRequest,
    session: Session = Depends(get_db),
    hindsight_client: HindsightClient = Depends(get_hindsight_client),
    ai_manager: Optional[AIProviderManager] = Depends(get_ai_manager),
) -> HistoricalIntelligenceResponse:
    """Execute unified historical intelligence query."""
    return await HistoricalIntelligenceService.ask(
        session=session,
        product=payload.product,
        question=payload.question,
        hindsight_client=hindsight_client,
        ai_manager=ai_manager,
    )
