import sqlite3
from unittest import TestCase

from job_hunter_agent.infrastructure.repository import SqliteJobRepository
from job_hunter_agent.infrastructure.schema_migrations import CURRENT_SCHEMA_VERSION


class RepositorySchemaBootstrapTests(TestCase):
    def test_repository_startup_registers_current_schema_version(self) -> None:
        connection = sqlite3.connect(":memory:")
        repository = SqliteJobRepository(":memory:")

        # Use the repository connection helper so the assertion covers the
        # startup path installed by the infrastructure package bootstrap.
        with repository._connect() as connection:
            rows = connection.execute(
                """
                SELECT version, name, applied_at_utc
                FROM schema_migrations
                ORDER BY version ASC
                """
            ).fetchall()

        self.assertEqual(1, len(rows))
        self.assertEqual(CURRENT_SCHEMA_VERSION, rows[0][0])
        self.assertTrue(rows[0][2].endswith("+00:00"))
