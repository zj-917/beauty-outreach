"""Application factory and ASGI entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import APP_VERSION
from app.api.audit import router as audit_router
from app.api.errors import register_exception_handlers
from app.api.middleware import AdminAuthMiddleware, RequestContextMiddleware
from app.api.system import router as system_router
from app.core.clock import Clock, SystemClock
from app.core.config import Settings
from app.core.db import build_engine, build_session_factory
from app.core.logging import configure_logging
from app.domain.masking import redact_log_text
from app.models import create_schema


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Release the database engine when the application stops."""
    yield
    app.state.engine.dispose()


def create_app(
    *,
    settings: Settings | None = None,
    clock: Clock | None = None,
    messenger: object | None = None,
) -> FastAPI:
    """Build the FastAPI application with injectable collaborators."""
    settings = settings or Settings()
    configure_logging(settings.log_level, redactor=redact_log_text)
    app = FastAPI(title="Beauty Outreach", version=APP_VERSION, lifespan=lifespan)
    engine = build_engine(settings)
    create_schema(engine)
    app.state.settings = settings
    app.state.clock = clock or SystemClock()
    app.state.messenger = messenger
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    app.state.worker_status = "disabled"

    register_exception_handlers(app)
    app.add_middleware(AdminAuthMiddleware, admin_token=settings.admin_token)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(system_router)
    app.include_router(audit_router)
    return app


def __getattr__(name: str) -> FastAPI:
    """Build the ASGI app lazily so importing the factory needs no environment."""
    if name == "app":
        application = create_app()
        globals()["app"] = application
        return application
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
