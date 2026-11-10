"""API routes for Theme Discovery & Lifecycle Management (Part 7 - Hackathon Prototype)."""

from typing import List, Optional
import uuid

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.theme import (
    ActivateThemeRequest,
    DiscoverThemesRequest,
    DiscoverThemesResponse,
    MergeThemesRequest,
    MergeThemesResponse,
    ThemeResponse,
)
from app.services.theme_lifecycle_service import ThemeLifecycleService

router = APIRouter()


@router.post(
    "/discover",
    response_model=DiscoverThemesResponse,
    status_code=status.HTTP_200_OK,
    summary="Discover Candidate Themes",
    description="Run clustering on unassigned feedback and stage qualifying clusters as candidate themes.",
)
def discover_themes(
    request: DiscoverThemesRequest,
    session: Session = Depends(get_db),
) -> DiscoverThemesResponse:
    """Discover and persist candidate themes using hierarchical clustering."""
    return ThemeLifecycleService.discover_and_stage_candidates(
        session=session,
        product=request.product,
        similarity_threshold=request.similarity_threshold,
        min_cluster_size=request.min_cluster_size,
        max_batch_size=request.max_batch_size,
    )


@router.get(
    "",
    response_model=List[ThemeResponse],
    status_code=status.HTTP_200_OK,
    summary="List Themes",
    description="Retrieve themes for a product with optional status filtering (candidate, active, merged, discarded).",
)
def list_themes(
    product: str = Query(..., description="Target product line identifier"),
    theme_status: Optional[str] = Query(
        None, alias="status", description="Filter by status: candidate, active, merged, discarded"
    ),
    session: Session = Depends(get_db),
) -> List[ThemeResponse]:
    """List themes with member counts and representative feedback excerpts."""
    return ThemeLifecycleService.list_themes(
        session=session,
        product=product,
        status=theme_status,
    )


@router.get(
    "/{theme_id}",
    response_model=ThemeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Theme Details",
    description="Retrieve complete theme details, representative feedback, and sentiment summary.",
)
def get_theme(
    theme_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> ThemeResponse:
    """Get theme details and sentiment analytics."""
    return ThemeLifecycleService.get_theme_detail(
        session=session,
        theme_id=theme_id,
    )


@router.post(
    "/{theme_id}/activate",
    response_model=ThemeResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate Candidate Theme",
    description="Promote a candidate theme to active status, optionally renaming or editing metadata.",
)
def activate_theme(
    theme_id: uuid.UUID,
    request: Optional[ActivateThemeRequest] = Body(None),
    session: Session = Depends(get_db),
) -> ThemeResponse:
    """Activate a candidate theme."""
    custom_name = request.custom_name if request else None
    category = request.category if request else None
    description = request.description if request else None

    return ThemeLifecycleService.activate_candidate(
        session=session,
        theme_id=theme_id,
        custom_name=custom_name,
        category=category,
        description=description,
    )


@router.post(
    "/{theme_id}/discard",
    response_model=ThemeResponse,
    status_code=status.HTTP_200_OK,
    summary="Discard Candidate Theme",
    description="Mark a candidate theme as discarded so it is no longer pending review.",
)
def discard_theme(
    theme_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> ThemeResponse:
    """Discard a candidate theme."""
    return ThemeLifecycleService.discard_candidate(
        session=session,
        theme_id=theme_id,
    )


@router.post(
    "/merge",
    response_model=MergeThemesResponse,
    status_code=status.HTTP_200_OK,
    summary="Merge Two Themes",
    description="Merge an active source theme into an active destination theme belonging to the same product.",
)
def merge_themes(
    request: MergeThemesRequest,
    session: Session = Depends(get_db),
) -> MergeThemesResponse:
    """Merge source theme into target theme."""
    return ThemeLifecycleService.merge_themes(
        session=session,
        source_theme_id=request.source_theme_id,
        target_theme_id=request.target_theme_id,
    )
