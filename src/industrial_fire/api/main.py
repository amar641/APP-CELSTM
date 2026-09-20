"""
FastAPI application entrypoint.

Run with `uv run python -m industrial_fire.api.main` — NOT the `uvicorn`
CLI directly. uvicorn (>=0.36) hardcodes a `ProactorEventLoop` on Windows
via its own `loop_factory` mechanism, which ignores `asyncio`'s event
loop policy entirely — so psycopg's async driver fails on the first real
query with `InterfaceError: Psycopg cannot use the 'ProactorEventLoop'`
no matter how early `core.windows_compat.ensure_selector_event_loop()`
runs. The `__main__` block below passes uvicorn `loop="asyncio:SelectorEventLoop"`
to override that on Windows; on Linux/macOS it's a no-op and behaves
identically to the CLI.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from industrial_fire.api.dependencies import get_continuous_pipeline
from industrial_fire.api.routes import aoi, events, facilities, health, pipeline
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


def _find_frontend_dist() -> Path | None:
    """
    Built by the Vite project under frontend/ (`npm run build`) — see
    frontend/README.md. Checked in two places because this file resolves
    to a different depth depending on how the package was installed: the
    dev source tree (`src/industrial_fire/api/main.py`, 3 parents up to the
    repo root) vs. the Docker image, where the package is pip-installed
    into site-packages but `frontend/dist` is copied to `WORKDIR/frontend/
    dist` (see Dockerfile) — i.e. relative to the process's cwd, not this
    file. Returns None (mount skipped) if neither exists, e.g. a dev
    checkout that hasn't run `npm run build` yet.
    """
    candidates = [
        Path(__file__).resolve().parents[3] / "frontend" / "dist",
        Path.cwd() / "frontend" / "dist",
    ]
    return next((c for c in candidates if c.is_dir()), None)


_FRONTEND_DIST = _find_frontend_dist()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    pipeline = get_continuous_pipeline()
    task = asyncio.create_task(pipeline.run_forever())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="Industrial Fire AI",
    description=(
        "AI-based detection and classification of industrial fires and persistent thermal "
        "sources using NASA FIRMS, OSM, weather, and satellite data."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # Same-origin in production (the dashboard is served by this app — see the
    # static mount below); this only matters for `npm run dev` against a local API.
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(health.router, prefix=API_PREFIX)
app.include_router(events.router, prefix=API_PREFIX)
app.include_router(facilities.router, prefix=API_PREFIX)
app.include_router(aoi.router, prefix=API_PREFIX)
app.include_router(pipeline.router, prefix=API_PREFIX)


@app.exception_handler(EntityNotFoundError)
async def handle_not_found(request: Request, exc: EntityNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ExternalServiceError)
async def handle_external_service_error(
    request: Request, exc: ExternalServiceError
) -> JSONResponse:
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


# Mounted last (and only if built) so /api/v1/* above always resolves first.
if _FRONTEND_DIST is not None:
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="dashboard")


if __name__ == "__main__":
    import uvicorn

    loop = "asyncio:SelectorEventLoop" if sys.platform == "win32" else "auto"
    uvicorn.run(app, host="0.0.0.0", port=settings.api_port, loop=loop)
