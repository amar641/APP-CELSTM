"""FastAPI application entrypoint. Run with `uvicorn industrial_fire.api.main:app`."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from industrial_fire.api.routes import events, facilities, health
from industrial_fire.core.config import get_settings
from industrial_fire.core.exceptions import (
    EntityNotFoundError,
    ExternalServiceError,
    IndustrialFireError,
    RepositoryError,
)
from industrial_fire.core.logging import configure_logging, get_logger
from industrial_fire.core.windows_compat import ensure_selector_event_loop

ensure_selector_event_loop()
configure_logging()
logger = get_logger(__name__)

settings = get_settings()

app = FastAPI(
    title="Industrial Fire AI",
    description=(
        "AI-based detection and classification of industrial fires and persistent thermal "
        "sources using NASA FIRMS, OSM, weather, and satellite data."
    ),
    version="0.1.0",
)

API_PREFIX = "/api/v1"
app.include_router(health.router, prefix=API_PREFIX)
app.include_router(events.router, prefix=API_PREFIX)
app.include_router(facilities.router, prefix=API_PREFIX)


@app.exception_handler(EntityNotFoundError)
async def handle_not_found(request: Request, exc: EntityNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ExternalServiceError)
async def handle_external_service_error(request: Request, exc: ExternalServiceError) -> JSONResponse:
    logger.warning("external service error: %s", exc)
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(RepositoryError)
async def handle_repository_error(request: Request, exc: RepositoryError) -> JSONResponse:
    logger.error("repository error: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "A storage backend is unavailable."})


@app.exception_handler(IndustrialFireError)
async def handle_generic_app_error(request: Request, exc: IndustrialFireError) -> JSONResponse:
    logger.exception("unhandled application error")
    return JSONResponse(status_code=500, content={"detail": str(exc)})
