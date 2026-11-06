from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_configuration_and_migration_discovery():
    """Verify that Alembic configuration is valid and all migrations in the chain are discoverable."""
    backend_dir = Path(__file__).resolve().parent.parent
    ini_path = backend_dir / "alembic.ini"
    assert ini_path.exists(), f"alembic.ini not found at {ini_path}"

    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    script_dir = ScriptDirectory.from_config(alembic_cfg)
    heads = script_dir.get_heads()

    # The head should be the Part 4.1 migration (content and metadata quality scores)
    assert len(heads) == 1, f"Expected 1 head revision, got {heads}"
    head_rev = heads[0]
    assert head_rev == "f6b903e1a82d"

    head_revision = script_dir.get_revision(head_rev)
    assert head_revision is not None
    assert "add_content_and_metadata_quality_scores" in head_revision.doc
    assert head_revision.down_revision == "e5a8f23c91d4"

    # Part 4 migration (feedback cleaning and quality fields)
    assert isinstance(head_revision.down_revision, str)
    part4_revision = script_dir.get_revision(head_revision.down_revision)
    assert part4_revision is not None
    assert part4_revision.revision == "e5a8f23c91d4"
    assert "add_feedback_cleaning_and_quality_fields" in part4_revision.doc
    assert isinstance(part4_revision.down_revision, str)
    assert part4_revision.down_revision == "c3f912b4e87a"

    # Part 3 migration (upload_jobs and safeguards)
    part3_revision = script_dir.get_revision(part4_revision.down_revision)
    assert part3_revision is not None
    assert part3_revision.revision == "c3f912b4e87a"
    assert "add_upload_jobs_and_safeguards" in part3_revision.doc
    assert isinstance(part3_revision.down_revision, str)
    assert part3_revision.down_revision == "b702ef22d23b"

    # Part 2.1 schema refinement migration
    refine_revision = script_dir.get_revision(part3_revision.down_revision)
    assert refine_revision is not None
    assert refine_revision.revision == "b702ef22d23b"
    assert "refine_schema_provenance_and_constraints" in refine_revision.doc
    assert isinstance(refine_revision.down_revision, str)
    assert refine_revision.down_revision == "ae66156cfb1a"

    # Base initial migration
    base_revision = script_dir.get_revision(refine_revision.down_revision)
    assert base_revision is not None
    assert base_revision.revision == "ae66156cfb1a"
    assert "initial_schema" in base_revision.doc
    assert base_revision.down_revision is None

    # Verify callables on all revisions
    for rev in (head_revision, part4_revision, part3_revision, refine_revision, base_revision):
        module = rev.module
        assert hasattr(module, "upgrade") and callable(module.upgrade)
        assert hasattr(module, "downgrade") and callable(module.downgrade)
