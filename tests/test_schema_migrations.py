import sqlite3
from unittest import TestCase

from job_hunter_agent.infrastructure.schema_migrations import (
    CURRENT_SCHEMA_NAME,
    CURRENT_SCHEMA_VERSION,
    ensure_current_schema_version,
    list_schema_migrations,
)


class SchemaMigrationsTests(TestCase):
    def test_ensure_current_schema_version_creates_bookkeeping_table(self) -> None:
        connection = sqlite3.connect(":memory:")

        ensure_current_schema_version(connection)

        migrations = list_schema_migrations(connection)
        self.assertEqual(1, len(migrations))
        self.assertEqual(CURRENT_SCHEMA_VERSION, migrations[0].version)
        self.assertEqual(CURRENT_SCHEMA_NAME, migrations[0].name)
        self.assertTrue(migrations[0].applied_at_utc.endswith("+00:00"))

    def test_ensure_current_schema_version_is_idempotent(self) -> None:
        connection = sqlite3.connect(":memory:")

        ensure_current_schema_version(connection)
        first_migration = list_schema_migrations(connection)[0]
        ensure_current_schema_version(connection)

        migrations = list_schema_migrations(connection)
        self.assertEqual([first_migration], migrations)

    def test_ensure_current_schema_version_preserves_existing_legacy_tables(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")
        connection.execute("INSERT INTO jobs (id, title) VALUES (1, 'Backend Java')")

        ensure_current_schema_version(connection)

        row = connection.execute("SELECT id, title FROM jobs").fetchone()
        self.assertEqual((1, "Backend Java"), row)
        self.assertEqual(1, len(list_schema_migrations(connection)))
