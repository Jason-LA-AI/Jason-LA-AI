"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.dashboard import STATIC_DIRECTORY, router as dashboard_router
from app.api.router import api_router
from app.config.settings import settings


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )
    application.include_router(api_router, prefix=settings.api_prefix)
    application.include_router(dashboard_router)
    application.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIRECTORY)),
        name="static",
    )
    return application


app = create_application()
