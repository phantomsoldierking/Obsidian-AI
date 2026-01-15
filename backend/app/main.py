from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.security import LocalOnlyMiddleware
from app.services.container import build_container

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)

    container = build_container(settings)
    app.state.container = container

    if settings.watcher_enabled:
        container.watcher.start()

    try:
        logger.info("Running startup indexing")
        await container.indexer.full_index()
    except Exception:
        logger.exception("Initial indexing failed")

    yield

    container.watcher.stop()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(LocalOnlyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
