"""Tests for Safe Migration Downgrade in Part 6 Step 4 (e82b95f3c94d).

Verifies that:
1. Downgrade detects duplicate (feedback_id, classification_version) groups and aborts with a clear,
   actionable RuntimeError rather than deleting or overwriting historical execution records.
2. The database schema and all records remain completely intact and unchanged when downgrade is blocked.
3. When no duplicates exist, downgrade proceeds normally, removing run_number and restoring the constraint.
"""

from pathlib import Path
import uuid
import pytest
from sqlalchemy import (
    Column,
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
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic import op


@pytest.fixture
def alembic_migration_e8():
    """Load the e82b95f3c94d migration module."""
    backend_dir = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    script_dir = ScriptDirectory.from_config(cfg)
    rev = script_dir.get_revision("e82b95f3c94d")
    assert rev is not None
    return rev.module


def create_schema_with_run_number(engine):
    """Create feedback and feedback_classifications tables reflecting the post-upgrade state."""
    meta = MetaData()
    feedback_table = Table(
        "feedback",
        meta,
        Column("feedback_id", Uuid(), primary_key=True),
        Column("feedback_text", Text(), nullable=False),
    )
    fc_table = Table(
        "feedback_classifications",
        meta,
        Column("classification_id", Uuid(), primary_key=True),
        Column("feedback_id", Uuid(), nullable=False),
        Column("classification_version", String(50), nullable=False),
        Column("run_number", Integer(), nullable=False, default=1),
        Column("status", String(50), nullable=False),
        UniqueConstraint(
            "feedback_id",
            "classification_version",
            "run_number",
            name="uq_feedback_classifications_feedback_version_run",
        ),
    )
    meta.create_all(engine)
    return fc_table


def test_downgrade_aborts_when_duplicates_exist_and_preserves_database(alembic_migration_e8):
    """Verify downgrade aborts with an actionable error when duplicate runs exist and leaves DB unchanged."""
    engine = create_engine("sqlite:///:memory:")
    fc_table = create_schema_with_run_number(engine)

    fid1 = uuid.uuid4()
    fid2 = uuid.uuid4()

    with engine.connect() as conn:
        # Insert historical reclassifications: fid1 has run 1 and run 2; fid2 has run 1
        conn.execute(
            fc_table.insert().values(
                [
                    {
                        "classification_id": uuid.uuid4(),
                        "feedback_id": fid1,
                        "classification_version": "v1.0.0",
                        "run_number": 1,
                        "status": "classified",
                    },
                    {
                        "classification_id": uuid.uuid4(),
                        "feedback_id": fid1,
                        "classification_version": "v1.0.0",
                        "run_number": 2,
                        "status": "classified",
                    },
                    {
                        "classification_id": uuid.uuid4(),
                        "feedback_id": fid2,
                        "classification_version": "v1.0.0",
                        "run_number": 1,
                        "status": "classified",
                    },
                ]
            )
        )
        conn.commit()

        # Configure Alembic operation context
        ctx = MigrationContext.configure(conn, opts={"as_sql": False})
        op._proxy = Operations(ctx)

        # Attempting downgrade MUST abort with clear RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            alembic_migration_e8.downgrade()

        err_msg = str(exc_info.value)
        assert "Downgrade aborted" in err_msg
        assert "multiple historical execution runs" in err_msg
        assert "never automatically deleted or overwritten" in err_msg
        assert (fid1.hex in err_msg or str(fid1) in err_msg)

        # VERIFY DATABASE REMAINS COMPLETELY UNCHANGED:
        # 1. run_number column is still present
        inspector = inspect(conn)
        columns = [c["name"] for c in inspector.get_columns("feedback_classifications")]
        assert "run_number" in columns, "run_number column must not be dropped when downgrade aborts"

        # 2. All 3 records remain intact with their exact runs
        rows = conn.execute(
            select(
                fc_table.c.feedback_id,
                fc_table.c.classification_version,
                fc_table.c.run_number,
            ).order_by(fc_table.c.run_number)
        ).fetchall()
        assert len(rows) == 3
        fid1_runs = [r[2] for r in rows if r[0] == fid1]
        assert fid1_runs == [1, 2], "Historical runs 1 and 2 must remain fully intact"

        # 3. Constraint uq_feedback_classifications_feedback_version_run is still present
        uq_constraints = [u["name"] for u in inspector.get_unique_constraints("feedback_classifications")]
        assert "uq_feedback_classifications_feedback_version_run" in uq_constraints


def test_downgrade_succeeds_normally_when_no_duplicates_exist(alembic_migration_e8):
    """Verify downgrade succeeds normally and removes run_number when no duplicates exist."""
    engine = create_engine("sqlite:///:memory:")
    fc_table = create_schema_with_run_number(engine)

    fid1 = uuid.uuid4()
    fid2 = uuid.uuid4()

    with engine.connect() as conn:
        # Insert single runs (no duplicates)
        conn.execute(
            fc_table.insert().values(
                [
                    {
                        "classification_id": uuid.uuid4(),
                        "feedback_id": fid1,
                        "classification_version": "v1.0.0",
                        "run_number": 1,
                        "status": "classified",
                    },
                    {
                        "classification_id": uuid.uuid4(),
                        "feedback_id": fid2,
                        "classification_version": "v1.0.0",
                        "run_number": 1,
                        "status": "classified",
                    },
                ]
            )
        )
        conn.commit()

        ctx = MigrationContext.configure(conn, opts={"as_sql": False})
        op._proxy = Operations(ctx)

        # Downgrade must succeed without error
        alembic_migration_e8.downgrade()
        conn.commit()

        # Verify schema: run_number column is dropped and old constraint restored
        inspector = inspect(conn)
        columns = [c["name"] for c in inspector.get_columns("feedback_classifications")]
        assert "run_number" not in columns, "run_number column should be removed after clean downgrade"

        uq_constraints = [u["name"] for u in inspector.get_unique_constraints("feedback_classifications")]
        assert "uq_feedback_classifications_feedback_version" in uq_constraints
        assert "uq_feedback_classifications_feedback_version_run" not in uq_constraints
