from __future__ import annotations

from typing import Any, Callable

from job_hunter_agent.infrastructure.schema_migrations import ensure_current_schema_version


def install_schema_migration_bootstrap() -> None:
    """Ensure SqliteJobRepository records the current schema version on startup.

    The repository module is currently large and central to local persistence. This
    bootstrap keeps the migration registration isolated while preserving the
    existing table-creation flow and user data compatibility.
    """
    from job_hunter_agent.infrastructure import repository as repository_module

    repository_class = repository_module.SqliteJobRepository
    if getattr(repository_class, "_schema_migration_bootstrap_installed", False):
        return

    original_create_tables: Callable[[Any], None] = repository_class._create_tables

    def create_tables_and_register_schema(self: Any) -> None:
        original_create_tables(self)
        with self._connect() as connection:
            ensure_current_schema_version(connection)

    repository_class._create_tables = create_tables_and_register_schema
    repository_class._schema_migration_bootstrap_installed = True
