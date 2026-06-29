from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import enrichment
from app.config import get_settings
from app.db import close_db, init_db
from app.ingest import router as ingest_router
from app.litellm_source import litellm_poll_loop
from app.live import router as live_router
from app.routes_dashboard import router as dashboard_router
from app.snapshots import snapshot_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db(settings.db_path)
    loaded = enrichment.load_from_path(settings.participants_csv)
    logger.info("loaded %d participants from %s", loaded, settings.participants_csv)
    tasks = [asyncio.create_task(snapshot_loop())]
    if settings.litellm_enabled:
        logger.info("litellm source enabled; polling %s", settings.litellm_base_url)
        tasks.append(asyncio.create_task(litellm_poll_loop()))
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="CCDashboard Server", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(ingest_router)
    app.include_router(dashboard_router)
    app.include_router(live_router)
    _mount_frontend(app, settings.frontend_dist)
    return app


def _mount_frontend(app: FastAPI, dist: str) -> None:
    """Serve the built Vite SPA. No-op when the dist dir is absent (dev/tests).

    Registered after the API routers so /api and /ingest keep priority; the
    catch-all returns the requested static file if it exists, else index.html
    so deep links (React Router) resolve to the SPA shell.
    """
    if not os.path.isdir(dist):
        logger.info("frontend dist %s not found; running API-only", dist)
        return

    dist_abs = os.path.abspath(dist)
    assets_dir = os.path.join(dist_abs, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    index_file = os.path.join(dist_abs, "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        candidate = os.path.normpath(os.path.join(dist_abs, full_path))
        if (
            full_path
            and candidate.startswith(dist_abs + os.sep)
            and os.path.isfile(candidate)
        ):
            return FileResponse(candidate)
        return FileResponse(index_file)


app = create_app()
