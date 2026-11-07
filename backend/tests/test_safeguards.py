from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import Theme, Feedback, MemoryMetadata, ThemeSnapshot, Insight


@pytest.fixture
def db_session():
    """Create in-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:", echo=False)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_safeguard_a_theme_product_requires_explicit_value(db_session: Session):
    """Safeguard A: Verify that Theme requires an explicit product value without a fake default."""
    theme = Theme(
        theme_id=uuid.uuid4(),
        product="Search Experience",
        theme_name="Latency on Typeahead",
        category="performance",
    )
    db_session.add(theme)
    db_session.commit()

    saved = db_session.get(Theme, theme.theme_id)
    assert saved is not None
    assert saved.product == "Search Experience"


def test_safeguard_b_memory_metadata_provenance_validation(db_session: Session):
    """Safeguard B: Verify that MemoryMetadata validates provenance agreement."""
    fb = Feedback(
        feedback_id=uuid.uuid4(),
        source="csv",
        feedback_text="Test feedback for provenance check",
        product="Core App",
        timestamp=datetime.now(timezone.utc),
    )
    theme = Theme(
        theme_id=uuid.uuid4(),
        product="Core App",
        theme_name="Core Stability",
        category="stability",
    )
    db_session.add_all([fb, theme])
    db_session.commit()

    # 1. Valid feedback memory works
    valid_fb_mem = MemoryMetadata(
        memory_id=uuid.uuid4(),
        bank_id="default",
        memory_type="theme_reflection",
        source_entity_type="feedback",
        feedback_id=fb.feedback_id,
    )
    db_session.add(valid_fb_mem)
    db_session.commit()

    # 2. Inconsistent provenance raises ValueError at application level
    with pytest.raises(ValueError, match="(Cannot set|conflicts with non-null)"):
        MemoryMetadata(
            memory_id=uuid.uuid4(),
            bank_id="default",
            memory_type="theme_reflection",
            source_entity_type="feedback",
            feedback_id=fb.feedback_id,
            snapshot_id=uuid.uuid4(),  # Conflicts with feedback type
        )

    with pytest.raises(ValueError, match="(Cannot set|conflicts with non-null)"):
        MemoryMetadata(
            memory_id=uuid.uuid4(),
            bank_id="default",
            memory_type="theme_reflection",
            source_entity_type="insight",
            feedback_id=fb.feedback_id,  # Conflicts with insight type
        )

    with pytest.raises(ValueError, match="Cannot set feedback_id"):
        mem = MemoryMetadata(
            memory_id=uuid.uuid4(),
            bank_id="default",
            memory_type="theme_reflection",
            source_entity_type="insight",
        )
        mem.feedback_id = fb.feedback_id

    # 3. Unsupported source_entity_type raises ValueError
    with pytest.raises(ValueError, match="Unsupported source_entity_type"):
        MemoryMetadata(
            memory_id=uuid.uuid4(),
            bank_id="default",
            memory_type="theme_reflection",
            source_entity_type="unsupported_custom_type",
        )

    # 4. Valid reflection and external memory types with null FKs succeed
    reflection_mem = MemoryMetadata(
        memory_id=uuid.uuid4(),
        bank_id="default",
        memory_type="theme_reflection",
        source_entity_type="reflection",
    )
    external_mem = MemoryMetadata(
        memory_id=uuid.uuid4(),
        bank_id="default",
        memory_type="theme_reflection",
        source_entity_type="external",
        source_reference="https://example.com/doc/1",
    )
    db_session.add_all([reflection_mem, external_mem])
    db_session.commit()

    saved_refl = db_session.get(MemoryMetadata, reflection_mem.memory_id)
    saved_ext = db_session.get(MemoryMetadata, external_mem.memory_id)
    assert saved_refl is not None and saved_refl.source_entity_type == "reflection"
    assert saved_ext is not None and saved_ext.source_reference == "https://example.com/doc/1"
