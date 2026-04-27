import sqlite3
import unittest

from job_hunter_agent.infrastructure.sqlite_migrations import (
    CURRENT_SCHEMA_VERSION,
    SqliteMigration,
    current_schema_version,
    run_sqlite_migrations,
)


class SqliteMigrationTests(unittest.TestCase):
    def test_run_sqlite_migrations_registers_baseline_on_empty_database(self) -> None:
        connection = sqlite3.connect(":memory:")

        run_sqlite_migrations(connection)

        row = connection.execute(
            "SELECT version, name, applied_at FROM schema_migrations WHERE version = ?",
            (CURRENT_SCHEMA_VERSION,),
        ).fetchone()
        self.assertEqual(row[0], CURRENT_SCHEMA_VERSION)
        self.assertEqual(row[1], "baseline_current_schema")
        self.assertIn("+00:00", row[2])
        self.assertEqual(current_schema_version(connection), CURRENT_SCHEMA_VERSION)

    def test_run_sqlite_migrations_is_idempotent(self) -> None:
        connection = sqlite3.connect(":memory:")

        run_sqlite_migrations(connection)
        run_sqlite_migrations(connection)

        row = connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()
        self.assertEqual(row[0], 1)

    def test_run_sqlite_migrations_preserves_legacy_tables(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")
        connection.execute("INSERT INTO jobs (id, title) VALUES (1, 'Backend Java')")

        run_sqlite_migrations(connection)

        legacy_row = connection.execute("SELECT id, title FROM jobs WHERE id = 1").fetchone()
        self.assertEqual(legacy_row, (1, "Backend Java"))
        self.assertEqual(current_schema_version(connection), CURRENT_SCHEMA_VERSION)

    def test_run_sqlite_migrations_applies_pending_versions_in_order(self) -> None:
        applied: list[int] = []

        def apply_v2(connection: sqlite3.Connection) -> None:
            applied.append(2)
            connection.execute("CREATE TABLE example_v2 (id INTEGER PRIMARY KEY)")

        def apply_v3(connection: sqlite3.Connection) -> None:
            applied.append(3)
            connection.execute("CREATE TABLE example_v3 (id INTEGER PRIMARY KEY)")

        connection = sqlite3.connect(":memory:")
        migrations = (
            SqliteMigration(version=3, name="third", apply=apply_v3),
            SqliteMigration(version=2, name="second", apply=apply_v2),
        )

        run_sqlite_migrations(connection, migrations=migrations)

        self.assertEqual(applied, [2, 3])
        self.assertEqual(current_schema_version(connection), 3)
