"""SQLite engine and session helpers with WAL and BEGIN IMMEDIATE."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings

_SQLITE_PREFIX = "sqlite:///"


def _ensure_sqlite_directory(database_url: str) -> None:
    if not database_url.startswith(_SQLITE_PREFIX):
        return
    raw_path = database_url[len(_SQLITE_PREFIX) :]
    if not raw_path or raw_path.startswith(":memory:") or raw_path.startswith("file:"):
        return
    Path(raw_path).expanduser().parent.mkdir(parents=True, exist_ok=True)


def _set_sqlite_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def _begin_immediate(connection: Any) -> None:
    connection.exec_driver_sql("BEGIN IMMEDIATE")


def build_engine(settings: Settings) -> Engine:
    """Create the SQLAlchemy engine for the configured database."""
    _ensure_sqlite_directory(settings.database_url)
    connect_args = (
        {"check_same_thread": False, "timeout": 5}
        if settings.database_url.startswith("sqlite")
        else {}
    )
    engine = create_engine(settings.database_url, connect_args=connect_args)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _set_sqlite_pragmas)
        event.listen(engine, "begin", _begin_immediate)
    return engine


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory bound to the engine."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
