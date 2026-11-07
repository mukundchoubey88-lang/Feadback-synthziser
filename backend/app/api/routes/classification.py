"""API routes for classification aggregate analytics and summary statistics."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.db.session import get_db
from app.schemas.classification import ClassificationSummaryResponse
from app.services.feedback_classification import FeedbackClassificationService

router = APIRouter()


def parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 string, handling URL query space-decoded '+' for timezone offsets."""
    if not dt_str:
        return None
    cleaned = dt_str.strip()
    # If trailing offset has a space instead of '+' due to URL query decoding: e.g. " 00:00"
    if " " in cleaned and ("+" not in cleaned and not cleaned.endswith("Z")):
        parts = cleaned.rsplit(" ", 1)
        if len(parts) == 2 and ":" in parts[1]:
            cleaned = f"{parts[0]}+{parts[1]}"
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        raise AppException(
            message=f"Invalid ISO 8601 date format for timestamp '{dt_str}'.",
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_DATE_FORMAT",
        )


@router.get(
    "/summary",
    response_model=ClassificationSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Classification & Sentiment Summary",
    description=(
        "Retrieve aggregate classification metrics, sentiment distribution, customer intents, "
        "aspect sentiment distribution, human review flags, and feedback quality status distribution."
    ),
)
def get_classifications_summary(
    product: Optional[str] = Query(None, description="Optional product name filter"),
    start_date: Optional[str] = Query(None, description="Optional start timestamp filter (ISO 8601)"),
    end_date: Optional[str] = Query(None, description="Optional end timestamp filter (ISO 8601)"),
    session: Session = Depends(get_db),
) -> ClassificationSummaryResponse:
    """Retrieve aggregate classification statistics with database-side aggregation and historical deduplication."""
    parsed_start = parse_iso_datetime(start_date)
    parsed_end = parse_iso_datetime(end_date)

    return FeedbackClassificationService.get_classification_summary(
        session=session,
        product=product,
        start_date=parsed_start,
        end_date=parsed_end,
    )
