from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
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


@dataclass(frozen=True)
class SchemaMigrationStep:
    version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


def _baseline_current_schema(_connection: sqlite3.Connection) -> None:
    """Register the current SQLite schema as the first managed baseline."""


SCHEMA_MIGRATIONS: tuple[SchemaMigrationStep, ...] = (
    SchemaMigrationStep(
        version=CURRENT_SCHEMA_VERSION,
        name=CURRENT_SCHEMA_NAME,
        apply=_baseline_current_schema,
    ),
)


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


def applied_schema_versions(connection: sqlite3.Connection) -> set[int]:
    return {migration.version for migration in list_schema_migrations(connection)}


def current_schema_version(connection: sqlite3.Connection) -> int:
    migrations = list_schema_migrations(connection)
    if not migrations:
        return 0
    return max(migration.version for migration in migrations)


def run_schema_migrations(
    connection: sqlite3.Connection,
    migrations: Iterable[SchemaMigrationStep] = SCHEMA_MIGRATIONS,
) -> None:
    """Apply pending SQLite schema migrations idempotently.

    The baseline migration records the schema that existed before formal
    migration tracking. Future migrations must remain additive/idempotent so
    they can safely run on both empty and legacy local SQLite databases.
    """
    ensure_schema_migrations_table(connection)
    applied_versions = applied_schema_versions(connection)
    for migration in sorted(migrations, key=lambda item: item.version):
        if migration.version in applied_versions:
            continue
        migration.apply(connection)
        connection.execute(
            """
            INSERT INTO schema_migrations (version, name, applied_at_utc)
            VALUES (?, ?, ?)
            """,
            (migration.version, migration.name, utc_now_iso()),
        )
        applied_versions.add(migration.version)


def ensure_current_schema_version(
    connection: sqlite3.Connection,
    *,
    version: int = CURRENT_SCHEMA_VERSION,
    name: str = CURRENT_SCHEMA_NAME,
) -> None:
    """Register the current SQLite schema version idempotently."""
    run_schema_migrations(
        connection,
        migrations=(
            SchemaMigrationStep(
                version=version,
                name=name,
                apply=_baseline_current_schema,
            ),
        ),
    )
