"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import DEFAULT_JWT_SECRET, Settings, get_settings
from app.db import get_engine, init_db
from app.errors import install_error_handlers
from app.logging_setup import RequestIdMiddleware, configure_logging, get_logger
from app.routers import auth, chat, documents, stats
from app.services import vectorstore
from app.services.ingest import recover_interrupted

log = get_logger(__name__)


def validate_settings(settings: Settings) -> None:
    """Fail fast with a clear message when required configuration is missing."""
    if not settings.mock_llm and not settings.gemini_api_key.strip():
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add your Google AI Studio key to the repository-root "
            ".env file, or set MOCK_LLM=true to run offline with the built-in mock model."
        )
    if settings.chunk_overlap >= settings.chunk_size:
        raise RuntimeError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE.")
    if settings.jwt_secret == DEFAULT_JWT_SECRET:
        log.warning("JWT_SECRET is the default value. Set a long random secret before deploying.")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    validate_settings(settings)
    settings.uploads_path.mkdir(parents=True, exist_ok=True)
    init_db()
    recovered = recover_interrupted()
    if recovered:
        log.warning("marked %d interrupted document(s) as failed", recovered)
    vectorstore.get_collection()
    log.info("DocuMind ready (mock_llm=%s, mode=%s)", settings.mock_llm, settings.retrieval_mode)
    yield


def create_app() -> FastAPI:
    """Build the app: middleware, error handlers and routers."""
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title="DocuMind API",
        version="1.0.0",
        description="Upload documents and ask questions with cited answers.",
        lifespan=lifespan,
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    install_error_handlers(app)
    for router in (auth.router, documents.router, chat.router, stats.router):
        app.include_router(router, prefix="/api")

    @app.get("/health", tags=["health"])
    def health(response: Response) -> dict:
        """Liveness plus dependency checks."""
        status = {"status": "ok", "db": "ok", "chroma": "ok"}
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            status["db"] = "error"
        try:
            vectorstore.get_client().heartbeat()
        except Exception:
            status["chroma"] = "error"
        if "error" in status.values():
            status["status"] = "degraded"
            response.status_code = 503
        return status

    return app


app = create_app()
