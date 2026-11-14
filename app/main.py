"""Application factory and ASGI entry point."""

from __future__ import annotations

import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import APP_VERSION
from app.api.audit import router as audit_router
from app.api.campaign import router as campaign_router
from app.api.compliance import router as compliance_router
from app.api.config import router as config_router
from app.api.demo import router as demo_router
from app.api.errors import register_exception_handlers
from app.api.lead import router as lead_router
from app.api.middleware import AdminAuthMiddleware, RequestContextMiddleware
from app.api.pool import router as pool_router
from app.api.screening import router as screening_router
from app.api.system import router as system_router
from app.api.template import router as template_router
from app.api.webhook import router as webhook_router
from app.core.clock import Clock, SystemClock
from app.core.config import Settings, load_settings, validate_runtime_settings
from app.core.db import build_engine, build_session_factory
from app.core.logging import configure_logging
from app.core.security import PhoneCipher
from app.domain.masking import redact_log_text
from app.engine.processor import Processor
from app.engine.worker import Worker
from app.models import create_schema
from app.providers.messenger import MockMessenger
from app.services.audit_service import AuditService
from app.services.receipt_service import ReceiptService
from app.services.seed_service import database_is_empty, seed_defaults


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Seed an empty database, run the worker thread, and release resources."""
    if app.state.settings.seed_defaults:
        with app.state.session_factory() as session:
            if database_is_empty(session):
                seed_defaults(session, app.state.clock)
    worker: Worker | None = app.state.worker
    thread: threading.Thread | None = None
    if worker is not None:
        thread = threading.Thread(
            target=worker.run_forever, name="outreach-worker", daemon=True
        )
        thread.start()
    yield
    if worker is not None and thread is not None:
        worker.stop()
        thread.join(timeout=5)
    app.state.engine.dispose()


def create_app(
    *,
    settings: Settings | None = None,
    clock: Clock | None = None,
    messenger: object | None = None,
) -> FastAPI:
    """Build the FastAPI application with injectable collaborators."""
    if settings is None:
        settings = load_settings()
    else:
        validate_runtime_settings(settings)
    configure_logging(settings.log_level, redactor=redact_log_text)
    app = FastAPI(title="Beauty Outreach", version=APP_VERSION, lifespan=lifespan)
    engine = build_engine(settings)
    create_schema(engine)
    app.state.settings = settings
    app.state.clock = clock or SystemClock()
    app.state.audit_service = AuditService(app.state.clock)
    if messenger is None and settings.messenger_provider == "mock":
        messenger = MockMessenger(app.state.clock)
    app.state.messenger = messenger
    app.state.phone_cipher = PhoneCipher(
        settings.phone_enc_key, settings.phone_hash_key
    )
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    worker: Worker | None = None
    if settings.worker_enabled and messenger is not None:
        processor = Processor(
            app.state.clock,
            app.state.phone_cipher,
            messenger,
            worker_id="worker-1",
            audit=app.state.audit_service,
        )
        receipts = ReceiptService(
            app.state.clock,
            messenger=messenger,
            session_factory=app.state.session_factory,
        )
        worker = Worker(
            app.state.session_factory,
            app.state.clock,
            processor,
            worker_id="worker-1",
            tick_seconds=settings.tick_seconds,
            receipts=receipts,
        )
    app.state.worker = worker
    app.state.worker_status = "running" if worker is not None else "disabled"

    register_exception_handlers(app)
    app.add_middleware(AdminAuthMiddleware, admin_token=settings.admin_token)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(system_router)
    app.include_router(audit_router)
    app.include_router(campaign_router)
    app.include_router(config_router)
    app.include_router(compliance_router)
    app.include_router(lead_router)
    app.include_router(screening_router)
    app.include_router(pool_router)
    app.include_router(template_router)
    app.include_router(webhook_router)
    if settings.demo_mode:
        app.include_router(demo_router)
    return app


def __getattr__(name: str) -> FastAPI:
    """Build the ASGI app lazily so importing the factory needs no environment."""
    if name == "app":
        application = create_app()
        globals()["app"] = application
        return application
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
