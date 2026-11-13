"""Schema creation and append-only triggers for audit_log."""

from __future__ import annotations

from sqlalchemy import Engine

from app.models.base import Base

AUDIT_LOG_TRIGGERS = (
    """
    CREATE TRIGGER IF NOT EXISTS audit_log_no_update
    BEFORE UPDATE ON audit_log
    BEGIN
        SELECT RAISE(ABORT, 'audit_log is append-only');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
    BEFORE DELETE ON audit_log
    BEGIN
        SELECT RAISE(ABORT, 'audit_log is append-only');
    END
    """,
)


def create_schema(engine: Engine) -> None:
    """Create all tables, indexes and append-only triggers."""
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        for statement in AUDIT_LOG_TRIGGERS:
            connection.exec_driver_sql(statement)
