import pytest
from app.db.session import is_database_configured, get_db
from app.core.exceptions import DatabaseNotConfiguredError


def test_session_handling_when_unconfigured():
    """Verify that get_db raises DatabaseNotConfiguredError if database engine is not initialized."""
    # When DATABASE_URL is not set or empty in environment
    if not is_database_configured():
        gen = get_db()
        with pytest.raises(DatabaseNotConfiguredError):
            next(gen)
    else:
        # If configured, it yields a valid session
        gen = get_db()
        session = next(gen)
        assert session is not None
        session.close()
