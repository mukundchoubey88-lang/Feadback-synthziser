"""Tests for Feedback Embeddings Persistence, PortableVector, and Theme Lineage.

Verifies:
1. PortableVector type decorator on SQLite and dialect abstraction.
2. FeedbackEmbedding CRUD, cascade deletion with Feedback, and unique constraints.
3. Theme centroid vector storage and self-referential merge/split lineage.
4. Alembic migration upgrade and downgrade reversibility for revision b81c2d3e4f5a.
"""

from datetime import datetime, timezone
from pathlib import Path
import uuid
import pytest
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    create_engine,
    inspect,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic import op

from app.db.base import Base
from app.db.types import PortableVector
from app.models.feedback import Feedback
from app.models.feedback_embeddings import FeedbackEmbedding
from app.models.theme import Theme


def test_portable_vector_type_decorator():
    """Verify PortableVector type decorator binding, deserialization, and validation."""
    pv = PortableVector(dim=768)

    # Valid list of floats
    sample_vec = [0.123] * 768
    bound = pv.process_bind_param(sample_vec, dialect=create_engine("sqlite://").dialect)
    assert bound == sample_vec

    # Result value
    res = pv.process_result_value(sample_vec, dialect=create_engine("sqlite://").dialect)
    assert res == sample_vec

    # None handling
    assert pv.process_bind_param(None, dialect=create_engine("sqlite://").dialect) is None
    assert pv.process_result_value(None, dialect=create_engine("sqlite://").dialect) is None

    # Invalid non-list input raises ValueError
    with pytest.raises(ValueError, match="PortableVector expects a list of floats"):
        pv.process_bind_param("not-a-list", dialect=create_engine("sqlite://").dialect)


def test_feedback_embedding_crud_and_cascade_delete():
    """Verify FeedbackEmbedding storage, unique constraint, and cascade deletion."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # Create Feedback
        fb = Feedback(
            feedback_id=uuid.uuid4(),
            source="csv",
            customer_id="cust-201",
            feedback_text="Checkout fails on iOS 17 safari browser.",
            product="Checkout",
            timestamp=datetime.now(timezone.utc),
        )
        session.add(fb)
        session.flush()

        # Insert FeedbackEmbedding
        vec_768 = [0.01] * 768
        emb = FeedbackEmbedding(
            embedding_id=uuid.uuid4(),
            feedback_id=fb.feedback_id,
            embedding_model="gemini-embedding-2",
            embedding_dimensions=768,
            embedding_vector=vec_768,
            input_hash="sha256-checkout-ios17",
        )
        session.add(emb)
        session.commit()

        # Query and verify
        retrieved_emb = session.get(FeedbackEmbedding, emb.embedding_id)
        assert retrieved_emb is not None
        assert retrieved_emb.embedding_model == "gemini-embedding-2"
        assert retrieved_emb.embedding_dimensions == 768
        assert len(retrieved_emb.embedding_vector) == 768
        assert retrieved_emb.input_hash == "sha256-checkout-ios17"
        assert retrieved_emb.feedback.feedback_text == "Checkout fails on iOS 17 safari browser."

        # Verify UniqueConstraint on (feedback_id, embedding_model)
        duplicate_emb = FeedbackEmbedding(
            embedding_id=uuid.uuid4(),
            feedback_id=fb.feedback_id,
            embedding_model="gemini-embedding-2",  # Duplicate model for same feedback
            embedding_dimensions=768,
            embedding_vector=vec_768,
            input_hash="sha256-different-hash",
        )
        session.add(duplicate_emb)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # Verify CASCADE delete when Feedback is removed
        fb_to_delete = session.get(Feedback, fb.feedback_id)
        session.delete(fb_to_delete)
        session.commit()

        # Embedding must be cascade-deleted
        assert session.get(FeedbackEmbedding, emb.embedding_id) is None


def test_theme_centroid_and_lineage_tracking():
    """Verify Theme centroid_vector, merged_into_id, split_from_id, and lineage_metadata."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        vec_768 = [0.02] * 768

        # 1. Parent Theme A
        theme_a = Theme(
            theme_id=uuid.uuid4(),
            product="Checkout",
            theme_name="Payment Gateway Failures",
            category="bug",
            status="active",
            centroid_vector=vec_768,
            lineage_metadata={"action": "created_via_clustering", "cluster_size": 15},
        )
        session.add(theme_a)
        session.flush()

        # 2. Source Theme B merged into A
        theme_b = Theme(
            theme_id=uuid.uuid4(),
            product="Checkout",
            theme_name="Apple Pay Failures",
            category="bug",
            status="merged",
            centroid_vector=vec_768,
            merged_into_id=theme_a.theme_id,
            lineage_metadata={"action": "merged_into", "target_theme_id": str(theme_a.theme_id)},
        )
        session.add(theme_b)

        # 3. Child Theme C split from A
        theme_c = Theme(
            theme_id=uuid.uuid4(),
            product="Checkout",
            theme_name="Safari Biometric Token Error",
            category="bug",
            status="candidate",
            centroid_vector=vec_768,
            split_from_id=theme_a.theme_id,
            lineage_metadata={"action": "split_from", "parent_theme_id": str(theme_a.theme_id)},
        )
        session.add(theme_c)
        session.commit()

        # Query and verify
        retrieved_a = session.get(Theme, theme_a.theme_id)
        assert retrieved_a is not None
        assert retrieved_a.centroid_vector is not None
        assert len(retrieved_a.centroid_vector) == 768
        assert retrieved_a.lineage_metadata["cluster_size"] == 15
        assert len(retrieved_a.merged_sources) == 1
        assert retrieved_a.merged_sources[0].theme_name == "Apple Pay Failures"
        assert len(retrieved_a.split_children) == 1
        assert retrieved_a.split_children[0].theme_name == "Safari Biometric Token Error"

        retrieved_b = session.get(Theme, theme_b.theme_id)
        assert retrieved_b.status == "merged"
        assert retrieved_b.merged_into.theme_name == "Payment Gateway Failures"


def test_alembic_migration_b81c2d3e4f5a_cycle():
    """Verify upgrade and downgrade cycle for migration b81c2d3e4f5a."""
    backend_dir = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    script_dir = ScriptDirectory.from_config(cfg)
    rev = script_dir.get_revision("b81c2d3e4f5a")
    assert rev is not None
    migration_mod = rev.module

    engine = create_engine("sqlite:///:memory:", echo=False)

    # Pre-create prerequisites representing state at e82b95f3c94d
    meta = MetaData()
    Table(
        "feedback",
        meta,
        Column("feedback_id", Uuid(), primary_key=True),
        Column("source", String(100), nullable=False),
        Column("feedback_text", Text(), nullable=False),
        Column("product", String(100), nullable=False),
        Column("timestamp", DateTime(timezone=True), nullable=False),
    )
    Table(
        "themes",
        meta,
        Column("theme_id", Uuid(), primary_key=True),
        Column("product", String(100), nullable=False),
        Column("theme_name", String(150), nullable=False),
        Column("category", String(100), nullable=False),
        Column("status", String(50), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )
    meta.create_all(engine)

    # Execute UPGRADE
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        op._proxy = Operations(ctx)
        migration_mod.upgrade()
        conn.commit()

    # Verify upgrade changes
    insp = inspect(engine)
    table_names = insp.get_table_names()
    assert "feedback_embeddings" in table_names

    fe_cols = {col["name"]: col for col in insp.get_columns("feedback_embeddings")}
    assert "embedding_id" in fe_cols
    assert "feedback_id" in fe_cols
    assert "embedding_model" in fe_cols
    assert "embedding_dimensions" in fe_cols
    assert "embedding_vector" in fe_cols
    assert "input_hash" in fe_cols
    assert "created_at" in fe_cols

    theme_cols = {col["name"]: col for col in insp.get_columns("themes")}
    assert "centroid_vector" in theme_cols
    assert "merged_into_id" in theme_cols
    assert "split_from_id" in theme_cols
    assert "lineage_metadata" in theme_cols

    # Execute DOWNGRADE
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        op._proxy = Operations(ctx)
        migration_mod.downgrade()
        conn.commit()

    # Verify downgrade changes
    insp = inspect(engine)
    table_names = insp.get_table_names()
    assert "feedback_embeddings" not in table_names

    theme_cols_after = {col["name"]: col for col in insp.get_columns("themes")}
    assert "centroid_vector" not in theme_cols_after
    assert "merged_into_id" not in theme_cols_after
    assert "split_from_id" not in theme_cols_after
    assert "lineage_metadata" not in theme_cols_after
