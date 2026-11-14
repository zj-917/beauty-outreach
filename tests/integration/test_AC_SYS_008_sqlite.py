"""SQLite pragmas, constraints and transaction behaviour."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

TS = "2026-11-14 09:00:00"

EXPECTED_TABLES = {
    "keyword",
    "lead_batch",
    "lead",
    "contact_consent",
    "suppression",
    "template",
    "rate_rule",
    "system_setting",
    "campaign_task",
    "task_item",
    "send_log",
    "audit_log",
}

EXPECTED_INDEXES = {
    "ix_lead_status_score",
    "ix_lead_batch_id",
    "uq_lead_phone_hash",
    "uq_suppression_type_phone",
    "uq_suppression_type_username",
    "ix_task_item_task_status",
    "ix_task_item_status_next",
    "ix_task_item_phone_hash",
    "ix_task_item_provider_message_id",
    "ix_send_log_item_id",
    "ix_send_log_task_created",
    "ix_send_log_phone_phase_outcome_created",
    "ix_audit_log_entity",
    "ix_audit_log_ts",
}

EXPECTED_TRIGGERS = {"audit_log_no_update", "audit_log_no_delete"}


def _names(db: Engine, kind: str) -> set[str]:
    with db.connect() as connection:
        rows = connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type = ?", (kind,)
        ).scalars()
        return set(rows.all())


def _seed_campaign_graph(db: Engine) -> None:
    with db.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO lead_batch "
            "(source_type, source_name, total_rows, imported, duplicates, invalid, warnings, "
            "errors, created_by, created_at) "
            "VALUES ('MOCK', 'mock', 2, 2, 0, 0, 0, '[]', 'admin', ?)",
            (TS,),
        )
        for username in ("u1", "u2"):
            connection.exec_driver_sql(
                "INSERT INTO lead (batch_id, username, status, created_at, updated_at) "
                "VALUES (1, ?, 'NEW', ?, ?)",
                (username, TS, TS),
            )
        connection.exec_driver_sql(
            "INSERT INTO template "
            "(name, version, language, body, status, created_by, created_at) "
            "VALUES ('greeting', 1, 'en', 'hi', 'APPROVED', 'admin', ?)",
            (TS,),
        )
        connection.exec_driver_sql(
            "INSERT INTO campaign_task "
            "(name, template_id, status, selection, total_items, consecutive_failures, "
            "created_by, created_at, updated_at) "
            "VALUES ('c1', 1, 'DRAFT', '{}', 2, 0, 'admin', ?, ?)",
            (TS, TS),
        )


def _insert_task_item(connection: Connection, key: str, lead_id: int) -> None:
    connection.exec_driver_sql(
        "INSERT INTO task_item "
        "(task_id, lead_id, idempotency_key, status, attempts, created_at, updated_at) "
        "VALUES (1, ?, ?, 'PENDING', 0, ?, ?)",
        (lead_id, key, TS, TS),
    )


def test_AC_SYS_008_pragmas_are_applied(db: Engine) -> None:
    """Given a fresh database, when connected, then WAL, foreign keys and busy timeout are set."""
    with db.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar() >= 5000


def test_AC_SYS_008_schema_has_tables_indexes_and_triggers(db: Engine) -> None:
    """Given schema creation, when inspected, then all tables, indexes and triggers exist."""
    assert _names(db, "table") >= EXPECTED_TABLES
    assert _names(db, "index") >= EXPECTED_INDEXES
    assert _names(db, "trigger") >= EXPECTED_TRIGGERS


def test_AC_SYS_008_foreign_keys_are_enforced(db: Engine) -> None:
    """Given foreign keys on, when a dangling task_item row is inserted, then it fails."""
    with pytest.raises(IntegrityError), db.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO task_item "
            "(task_id, lead_id, idempotency_key, status, attempts, created_at, updated_at) "
            "VALUES (999, 999, 'fk-test', 'PENDING', 0, ?, ?)",
            (TS, TS),
        )


def test_AC_SYS_008_write_transactions_begin_immediate(db: Engine) -> None:
    """Given a write transaction, when traced, then it opens with BEGIN IMMEDIATE."""
    statements: list[str] = []
    with db.connect() as connection:
        driver = connection.connection.driver_connection
        driver.set_trace_callback(statements.append)
        try:
            with connection.begin():
                connection.exec_driver_sql(
                    "INSERT INTO keyword "
                    "(term, kind, weight, enabled, created_at, updated_at) "
                    "VALUES ('probe', 'POSITIVE', 1, 1, ?, ?)",
                    (TS, TS),
                )
        finally:
            driver.set_trace_callback(None)
    assert any(statement.strip().upper() == "BEGIN IMMEDIATE" for statement in statements)


def test_AC_SYS_008_task_item_unique_pair_rejected(db: Engine) -> None:
    """Given two items for the same task and lead, when inserted, then the unique pair fails."""
    _seed_campaign_graph(db)
    with db.begin() as connection:
        _insert_task_item(connection, "key-1", 1)
    with pytest.raises(IntegrityError), db.begin() as connection:
        _insert_task_item(connection, "key-2", 1)


def test_AC_SYS_008_task_item_idempotency_key_is_globally_unique(db: Engine) -> None:
    """Given a reused idempotency key across tasks, when inserted, then it fails."""
    _seed_campaign_graph(db)
    with db.begin() as connection:
        _insert_task_item(connection, "shared-key", 1)
    with pytest.raises(IntegrityError), db.begin() as connection:
        _insert_task_item(connection, "shared-key", 2)


def test_AC_SYS_008_suppression_partial_unique_indexes(db: Engine) -> None:
    """Given partial indexes, when duplicate phone or username is added, then it fails."""
    insert_sql = (
        "INSERT INTO suppression "
        "(type, phone_hash, phone_masked, username, reason, source, created_at, created_by) "
        "VALUES ('BLACKLIST', ?, NULL, ?, 'r', 'MANUAL', ?, 'admin')"
    )
    with db.begin() as connection:
        connection.exec_driver_sql(insert_sql, ("hash-1", None, TS))
    with pytest.raises(IntegrityError), db.begin() as connection:
        connection.exec_driver_sql(insert_sql, ("hash-1", None, TS))
    with db.begin() as connection:
        connection.exec_driver_sql(insert_sql, (None, "u1", TS))
    with pytest.raises(IntegrityError), db.begin() as connection:
        connection.exec_driver_sql(insert_sql, (None, "u1", TS))
    with db.begin() as connection:
        connection.exec_driver_sql(insert_sql, (None, "u2", TS))


def test_AC_SYS_008_read_transactions_also_begin_immediate(db: Engine) -> None:
    """Given a read-only statement, when traced, then it also opens with BEGIN IMMEDIATE."""
    statements: list[str] = []
    with db.connect() as connection:
        driver = connection.connection.driver_connection
        driver.set_trace_callback(statements.append)
        try:
            connection.exec_driver_sql("SELECT 1").scalar()
        finally:
            driver.set_trace_callback(None)
    assert any(statement.strip().upper() == "BEGIN IMMEDIATE" for statement in statements)


def test_AC_SYS_008_lead_phone_hash_is_unique_when_present(db: Engine) -> None:
    """Given two leads with the same phone hash, when inserted, then the partial index fails."""
    _seed_campaign_graph(db)
    insert_sql = (
        "INSERT INTO lead (batch_id, username, phone_hash, status, created_at, updated_at) "
        "VALUES (1, ?, ?, 'NEW', ?, ?)"
    )
    with db.begin() as connection:
        connection.exec_driver_sql(insert_sql, ("u3", "hash-1", TS, TS))
        connection.exec_driver_sql(insert_sql, ("u4", None, TS, TS))
    with pytest.raises(IntegrityError), db.begin() as connection:
        connection.exec_driver_sql(insert_sql, ("u5", "hash-1", TS, TS))


def test_AC_SYS_008_template_version_must_be_positive(db: Engine) -> None:
    """Given version 0, when inserted, then the check constraint rejects it."""
    with pytest.raises(IntegrityError), db.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO template "
            "(name, version, language, body, status, created_by, created_at) "
            "VALUES ('greeting', 0, 'en', 'hi', 'DRAFT', 'admin', ?)",
            (TS,),
        )
