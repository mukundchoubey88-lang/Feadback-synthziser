import logging
import sys
from app.core.config import settings


def setup_logging() -> None:
    """Configure centralized application logging."""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    # Custom log format
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Suppress overly chatty third-party loggers if not in debug
    if not settings.DEBUG:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logger = logging.getLogger("app")
    logger.info("Logging configured successfully with level: %s", logging.getLevelName(log_level))
