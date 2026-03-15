import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from apps.api.routes.artifacts import router as artifacts_router
from apps.api.routes.jobs import router as jobs_router
from apps.api.routes.runs import router as runs_router
from apps.api.routes.ws import router as ws_router
from apps.api.settings import Settings
from core.db import Base  # imports models, registering them with Base.metadata
from core.db.session import async_engine
from core.logging_config import configure_logging

settings = Settings()
configure_logging(app_env=settings.app_env, level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.debug(
        "API startup with app_env=%s log_level=%s artifact_dir=%s profile_dir=%s",
        settings.app_env,
        settings.log_level,
        settings.artifact_dir,
        settings.profile_dir,
    )
    Path(settings.artifact_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.profile_dir).mkdir(parents=True, exist_ok=True)
    # Create all tables on startup
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS source_payload_json JSONB")
        )
        await conn.execute(
            text("ALTER TABLE scrape_runs ADD COLUMN IF NOT EXISTS items_json JSONB")
        )
    yield


app = FastAPI(title="JobBot", lifespan=lifespan)
app.include_router(jobs_router)
app.include_router(artifacts_router)
app.include_router(runs_router)
app.include_router(ws_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        raise exc
    logger.exception("Unhandled API exception for path=%s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health")
async def health():
    return {"status": "ok"}
