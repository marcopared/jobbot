import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from apps.api.routes.artifacts import router as artifacts_router
from apps.api.routes.debug import router as debug_router
from apps.api.routes.jobs import router as jobs_router
from apps.api.routes.runs import router as runs_router
from apps.api.routes.ws import router as ws_router
from apps.api.settings import Settings
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
    # Schema is managed by Alembic. Run `alembic upgrade head` before startup.
    yield


app = FastAPI(title="JobBot", lifespan=lifespan)
app.include_router(jobs_router)
app.include_router(artifacts_router)
app.include_router(runs_router)
app.include_router(debug_router)
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
