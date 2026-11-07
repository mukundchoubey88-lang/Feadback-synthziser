from typing import Any, Optional
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger("app.exceptions")


class AppException(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        code: str = "INTERNAL_SERVER_ERROR",
        details: Optional[Any] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details


class ConfigurationError(AppException):
    """Raised when essential configuration is missing or invalid."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=500,
            code="CONFIGURATION_ERROR",
            details=details,
        )


class DatabaseNotConfiguredError(AppException):
    """Raised when a database operation is requested but DATABASE_URL is not configured."""

    def __init__(self, message: str = "Database connection is not configured."):
        super().__init__(
            message=message,
            status_code=503,
            code="DATABASE_NOT_CONFIGURED",
        )


class InvalidUploadError(AppException):
    """Raised when an uploaded file or payload violates structure, format, or size constraints."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=400,
            code="INVALID_UPLOAD",
            details=details,
        )


class PayloadTooLargeError(AppException):
    """Raised when an uploaded file exceeds the maximum allowed file size."""

    def __init__(self, message: str = "Uploaded file exceeds maximum allowed size limit.", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=413,
            code="PAYLOAD_TOO_LARGE",
            details=details,
        )


class EntityNotFoundError(AppException):
    """Raised when a requested resource (e.g., feedback or job) cannot be found."""

    def __init__(self, message: str = "Resource not found.", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=404,
            code="NOT_FOUND",
            details=details,
        )


async def app_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle custom application exceptions."""
    app_exc = exc if isinstance(exc, AppException) else AppException(str(exc))
    logger.error("AppException [%s]: %s (path: %s)", app_exc.code, app_exc.message, request.url.path)
    return JSONResponse(
        status_code=app_exc.status_code,
        content={
            "error": {
                "code": app_exc.code,
                "message": app_exc.message,
                "details": app_exc.details,
            }
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions to avoid exposing raw stack traces."""
    logger.exception("Unhandled server exception at %s: %s", request.url.path, str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please try again later.",
                "details": None,
            }
        },
    )
