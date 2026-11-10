"""API routes for Hindsight Persistent Memory Integration (Part 9).

Endpoints:
- POST /api/memory/sync: Selectively synchronizes PostgreSQL feedback/themes/releases/insights to Hindsight
- POST /api/memory/recall: Recalls relevant historical memories with PostgreSQL provenance
- POST /api/memory/reflect: Queries Hindsight for synthesized historical reasoning and trajectories
- GET /api/memory/status: Checks Hindsight service availability and local memory synchronization counts
"""

import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.integrations.hindsight.client import HindsightClient
from app.schemas.memory import (
    MemoryRecallRequest,
    MemoryRecallResponse,
    MemoryReflectRequest,
    MemoryReflectResponse,
    MemoryStatusResponse,
    MemorySyncRequest,
    MemorySyncResponse,
)
from app.services import hindsight_service

logger = logging.getLogger(__name__)

router = APIRouter()


def get_hindsight_client() -> HindsightClient:
    """Dependency provider for Hindsight REST API client."""
    return HindsightClient()


@router.post(
    "/sync",
    response_model=MemorySyncResponse,
    status_code=status.HTTP_200_OK,
    summary="Synchronize PostgreSQL records to Hindsight memory bank",
    description="Curates high-signal feedback, active themes, snapshots, releases, and insights into Hindsight.",
)
async def sync_memories(
    payload: MemorySyncRequest,
    session: Session = Depends(get_db),
    client: HindsightClient = Depends(get_hindsight_client),
) -> MemorySyncResponse:
    """Perform selective synchronization with duplicate prevention."""
    return await hindsight_service.sync_product_memories(
        session=session,
        product=payload.product,
        client=client,
        dry_run=payload.dry_run,
    )


@router.post(
    "/recall",
    response_model=MemoryRecallResponse,
    status_code=status.HTTP_200_OK,
    summary="Recall historical memories",
    description="Recalls relevant memories from Hindsight, enriched with local PostgreSQL provenance.",
)
async def recall_memories(
    payload: MemoryRecallRequest,
    session: Session = Depends(get_db),
    client: HindsightClient = Depends(get_hindsight_client),
) -> MemoryRecallResponse:
    """Recall historical memories for a product context."""
    return await hindsight_service.recall_memories(
        session=session,
        product=payload.product,
        query=payload.query,
        limit=payload.limit,
        client=client,
    )


@router.post(
    "/reflect",
    response_model=MemoryReflectResponse,
    status_code=status.HTTP_200_OK,
    summary="Reflect on historical memories",
    description="Requests synthesized reasoning and temporal analysis across historical memories.",
)
async def reflect_memories(
    payload: MemoryReflectRequest,
    session: Session = Depends(get_db),
    client: HindsightClient = Depends(get_hindsight_client),
) -> MemoryReflectResponse:
    """Reflect over historical customer trajectories and product evolution."""
    return await hindsight_service.reflect_on_memories(
        session=session,
        product=payload.product,
        query=payload.query,
        client=client,
    )


@router.get(
    "/status",
    response_model=MemoryStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Hindsight integration status",
    description="Checks service configuration, health, and local memory metadata volume.",
)
async def memory_status(
    session: Session = Depends(get_db),
    client: HindsightClient = Depends(get_hindsight_client),
) -> MemoryStatusResponse:
    """Return live availability and sync statistics."""
    return await hindsight_service.get_memory_status(
        session=session,
        client=client,
    )
