from contextlib import asynccontextmanager
import logging
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth_routes import router as auth_router
from app.api.routes import router
from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.security import ApiProtectionMiddleware


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.http_client = httpx.AsyncClient(timeout=settings.ai_timeout_seconds)
    app.state.database_engine = create_engine()
    app.state.session_factory = create_session_factory(app.state.database_engine)
    yield
    await app.state.http_client.aclose()
    await app.state.database_engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="昭星斋后端",
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(ApiProtectionMiddleware, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-Device-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    media_root = Path(settings.app_media_root)
    media_root.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=media_root), name="media")

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        logger.warning("request-validation-failed: %s", errors)
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder({"detail": errors}),
        )

    app.include_router(router)
    app.include_router(auth_router)
    return app


app = create_app()
