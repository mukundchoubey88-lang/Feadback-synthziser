from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import (
    Feedback,
    FeedbackThemes,
    Theme,
    ThemeSnapshot,
    SentimentHistory,
    ProductChanges,
    Insight,
    InsightEvidence,
    MemoryMetadata,
)


def test_metadata_registration():
    """Verify that all PRD models and tables are registered in Base.metadata."""
    table_names = set(Base.metadata.tables.keys())
    expected_tables = {
        "feedback",
        "themes",
        "feedback_themes",
        "sentiment_history",
        "product_changes",
        "theme_snapshots",
        "insights",
        "insight_evidence",
        "memory_metadata",
        "upload_jobs",
    }
    assert expected_tables.issubset(table_names), (
        f"Missing tables in metadata: {expected_tables - table_names}"
    )


def test_foreign_keys_and_primary_keys():
    """Verify that primary keys and foreign keys are defined as expected."""
    tables = Base.metadata.tables

    # Feedback
    fb_table = tables["feedback"]
    assert "feedback_id" in fb_table.primary_key.columns

    # Themes
    theme_table = tables["themes"]
    assert "theme_id" in theme_table.primary_key.columns

    # FeedbackThemes junction table (composite PK)
    ft_table = tables["feedback_themes"]
    assert "feedback_id" in ft_table.primary_key.columns
    assert "theme_id" in ft_table.primary_key.columns
    ft_fk_targets = {fk.target_fullname for fk in ft_table.foreign_keys}
    assert "feedback.feedback_id" in ft_fk_targets
    assert "themes.theme_id" in ft_fk_targets

    # SentimentHistory
    sh_table = tables["sentiment_history"]
    sh_fk_targets = {fk.target_fullname for fk in sh_table.foreign_keys}
    assert "feedback.feedback_id" in sh_fk_targets
    assert "themes.theme_id" in sh_fk_targets

    # InsightEvidence junction table (composite PK)
    ie_table = tables["insight_evidence"]
    assert "insight_id" in ie_table.primary_key.columns
    assert "feedback_id" in ie_table.primary_key.columns
    ie_fk_targets = {fk.target_fullname for fk in ie_table.foreign_keys}
    assert "insights.insight_id" in ie_fk_targets
    assert "feedback.feedback_id" in ie_fk_targets

    # MemoryMetadata
    mm_table = tables["memory_metadata"]
    mm_fk_targets = {fk.target_fullname for fk in mm_table.foreign_keys}
    assert "themes.theme_id" in mm_fk_targets
    assert "feedback.feedback_id" in mm_fk_targets
    assert "theme_snapshots.snapshot_id" in mm_fk_targets
    assert "insights.insight_id" in mm_fk_targets


    # UploadJob
    uj_table = tables["upload_jobs"]
    assert "job_id" in uj_table.primary_key.columns


def test_in_memory_sqlite_schema_and_crud():
    """Test full schema creation, relationships, and CRUD operations using isolated in-memory SQLite."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # 1. Create Feedback
        fb = Feedback(
            feedback_id=uuid.uuid4(),
            source="csv",
            customer_id="cust-101",
            feedback_text="The new dashboard loads very slowly on mobile devices.",
            product="Analytics Dashboard",
            feature="Mobile View",
            timestamp=datetime.now(timezone.utc),
            app_version="2.4.0",
        )
        session.add(fb)

        # 2. Create Theme (now product-scoped)
        theme = Theme(
            theme_id=uuid.uuid4(),
            product="Analytics Dashboard",
            theme_name="Dashboard Latency",
            description="Reports of high latency when accessing dashboard widgets",
            category="performance",
            status="active",
        )
        session.add(theme)
        session.flush()

        # 3. Associate via FeedbackThemes
        ft = FeedbackThemes(
            feedback_id=fb.feedback_id,
            theme_id=theme.theme_id,
            relevance_score=0.95,
            aspect_sentiment="negative",
        )
        session.add(ft)

        # 4. Record SentimentHistory
        sh = SentimentHistory(
            sentiment_id=uuid.uuid4(),
            feedback_id=fb.feedback_id,
            theme_id=theme.theme_id,
            sentiment_label="negative",
            sentiment_score=-0.75,
            confidence_score=0.92,
            analysed_at=datetime.now(timezone.utc),
        )
        session.add(sh)

        # 5. Record ProductChanges
        release = ProductChanges(
            release_id=uuid.uuid4(),
            product="Analytics Dashboard",
            feature="Widget Renderer",
            release_description="Redesigned charting framework to SVG-based rendering",
            release_date=datetime.now(timezone.utc),
            version="2.4.0",
            change_category="minor",
        )
        session.add(release)

        # 6. Record ThemeSnapshot
        snapshot = ThemeSnapshot(
            snapshot_id=uuid.uuid4(),
            theme_id=theme.theme_id,
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            feedback_count=12,
            positive_count=1,
            negative_count=10,
            neutral_count=1,
            sentiment_average=-0.65,
        )
        session.add(snapshot)

        # 7. Record Insight & InsightEvidence
        insight = Insight(
            insight_id=uuid.uuid4(),
            title="Mobile Performance Regression After v2.4.0",
            summary="Release 2.4.0 caused an 80% increase in negative feedback related to mobile widget rendering.",
            recommendation="Optimize SVG rendering pipeline and enable lazy loading for mobile viewports.",
            confidence_score=0.89,
            status="active",
        )
        session.add(insight)
        session.flush()

        evidence = InsightEvidence(
            insight_id=insight.insight_id,
            feedback_id=fb.feedback_id,
            evidence_type="direct_quote",
        )
        session.add(evidence)

        # 8. Record MemoryMetadata (Hindsight tracker layer with typed provenance)
        memory = MemoryMetadata(
            memory_id=uuid.uuid4(),
            bank_id="analytics-dashboard",
            hindsight_memory_id="hs-mem-ext-001",
            memory_type="theme_reflection",
            source_entity_type="feedback",
            feedback_id=fb.feedback_id,
            related_theme=theme.theme_id,
            source_reference="hs-mem-test-001",
        )
        session.add(memory)

        session.commit()

        # Query and verify associations
        retrieved_fb = session.get(Feedback, fb.feedback_id)
        assert retrieved_fb is not None
        assert retrieved_fb.feedback_text == "The new dashboard loads very slowly on mobile devices."
        assert len(retrieved_fb.feedback_themes) == 1
        assert retrieved_fb.feedback_themes[0].relevance_score == 0.95
        assert len(retrieved_fb.themes) == 1
        assert retrieved_fb.themes[0].theme_name == "Dashboard Latency"
        assert len(retrieved_fb.sentiment_history) == 1
        assert retrieved_fb.sentiment_history[0].sentiment_label == "negative"
        assert len(retrieved_fb.insights) == 1
        assert retrieved_fb.insights[0].title == "Mobile Performance Regression After v2.4.0"

        # Verify Theme relationships
        retrieved_theme = session.get(Theme, theme.theme_id)
        assert retrieved_theme is not None
        assert len(retrieved_theme.snapshots) == 1
        assert retrieved_theme.snapshots[0].feedback_count == 12
        assert len(retrieved_theme.memories) == 1
        assert retrieved_theme.memories[0].source_reference == "hs-mem-test-001"
