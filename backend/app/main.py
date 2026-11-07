from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import AppException, app_exception_handler, generic_exception_handler
from app.api.routes.health import router as health_router
from app.api.routes.feedback import router as feedback_router
from app.api.routes.classification import router as classification_router
from app.schemas.health import RootInfoResponse

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown routines."""
    # Startup
    setup_logging()
    logger.info("Starting up %s (env: %s)", settings.APP_NAME, settings.APP_ENV)
    yield
    # Shutdown
    logger.info("Shutting down %s", settings.APP_NAME)


def create_app() -> FastAPI:
    """Application factory for the FastAPI backend."""
    app = FastAPI(
        title="Feedback Intelligence API",
        version="1.0.0",
        description="Backend API for an AI-powered customer feedback intelligence and persistent memory platform.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Register API Routers
    app.include_router(health_router, prefix=settings.API_V1_PREFIX)
    app.include_router(
        feedback_router,
        prefix=f"{settings.API_V1_PREFIX}/feedback",
        tags=["Feedback"],
    )
    app.include_router(
        classification_router,
        prefix=f"{settings.API_V1_PREFIX}/classifications",
        tags=["Classification"],
    )

    # Root Endpoint
    @app.get(
        "/",
        response_model=RootInfoResponse,
        tags=["Root"],
        summary="Root Application Information",
    )
    async def root() -> RootInfoResponse:
        """Return basic metadata about the application and its documentation endpoints."""
        return RootInfoResponse(
            name=settings.APP_NAME,
            version="1.0.0",
            environment=settings.APP_ENV,
            docs_url="/docs",
            status="online",
        )

    return app


app = create_app()
