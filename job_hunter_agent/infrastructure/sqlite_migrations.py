from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone


CURRENT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SqliteMigration:
    version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _baseline_current_schema(_connection: sqlite3.Connection) -> None:
    """Registers the current SQLite schema as the first managed baseline."""


SQLITE_MIGRATIONS: tuple[SqliteMigration, ...] = (
    SqliteMigration(
        version=CURRENT_SCHEMA_VERSION,
        name="baseline_current_schema",
        apply=_baseline_current_schema,
    ),
)


def ensure_schema_migrations_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )


def applied_schema_versions(connection: sqlite3.Connection) -> set[int]:
    ensure_schema_migrations_table(connection)
    return {
        int(row[0])
        for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
    }


def current_schema_version(connection: sqlite3.Connection) -> int:
    ensure_schema_migrations_table(connection)
    row = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return int((row[0] if row else 0) or 0)


def run_sqlite_migrations(
    connection: sqlite3.Connection,
    migrations: Iterable[SqliteMigration] = SQLITE_MIGRATIONS,
) -> None:
    """Runs pending SQLite schema migrations idempotently.

    The first migration is a no-op baseline for the schema that existed before
    migration tracking. Future migrations should be additive and idempotent so
    they can run safely on both empty and legacy local SQLite databases.
    """
    ensure_schema_migrations_table(connection)
    applied_versions = applied_schema_versions(connection)
    for migration in sorted(migrations, key=lambda item: item.version):
        if migration.version in applied_versions:
            continue
        migration.apply(connection)
        connection.execute(
            """
            INSERT INTO schema_migrations (version, name, applied_at)
            VALUES (?, ?, ?)
            """,
            (migration.version, migration.name, _utc_now_iso()),
        )
        applied_versions.add(migration.version)
