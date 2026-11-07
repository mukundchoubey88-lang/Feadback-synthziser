from typing import Generator, Optional
import logging
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.core.exceptions import DatabaseNotConfiguredError

logger = logging.getLogger("app.db")

engine: Optional[Engine] = None
SessionLocal: Optional[sessionmaker] = None

if settings.DATABASE_URL:
    try:
        # Configure SQLAlchemy 2.x engine with connection pooling
        engine = create_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            pool_pre_ping=True,
            future=True,
        )
        SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
            expire_on_commit=False,
        )
        logger.info("Database engine initialized.")
    except Exception as exc:
        logger.warning("Failed to initialize database engine: %s", exc)
        engine = None
        SessionLocal = None
else:
    logger.info("DATABASE_URL not configured. Database engine not initialized.")


def is_database_configured() -> bool:
    """Check if the database connection string is configured and engine initialized."""
    return engine is not None and SessionLocal is not None


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session with automatic lifecycle cleanup.

    Raises:
        DatabaseNotConfiguredError: If DATABASE_URL is not configured.
    """
    if SessionLocal is None:
        raise DatabaseNotConfiguredError()

    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
