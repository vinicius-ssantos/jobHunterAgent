from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

CURRENT_SCHEMA_VERSION = 1
CURRENT_SCHEMA_NAME = "initial_sqlite_schema"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class SchemaMigration:
    version: int
    name: str
    applied_at_utc: str


def ensure_schema_migrations_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at_utc TEXT NOT NULL
        )
        """
    )


def ensure_current_schema_version(
    connection: sqlite3.Connection,
    *,
    version: int = CURRENT_SCHEMA_VERSION,
    name: str = CURRENT_SCHEMA_NAME,
) -> None:
    """Register the current SQLite schema version idempotently.

    This helper is intentionally conservative: it creates only the migration
    bookkeeping table and records the baseline version. It does not mutate user
    tables or rewrite existing local data.
    """
    ensure_schema_migrations_table(connection)
    connection.execute(
        """
        INSERT OR IGNORE INTO schema_migrations (version, name, applied_at_utc)
        VALUES (?, ?, ?)
        """,
        (version, name, utc_now_iso()),
    )


def list_schema_migrations(connection: sqlite3.Connection) -> list[SchemaMigration]:
    ensure_schema_migrations_table(connection)
    rows = connection.execute(
        """
        SELECT version, name, applied_at_utc
        FROM schema_migrations
        ORDER BY version ASC
        """
    ).fetchall()
    return [SchemaMigration(version=row[0], name=row[1], applied_at_utc=row[2]) for row in rows]
