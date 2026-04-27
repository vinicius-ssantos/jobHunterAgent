from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from job_hunter_agent.infrastructure.schema_migrations import ensure_current_schema_version


def install_schema_migration_bootstrap() -> None:
    """Ensure SqliteJobRepository records schema and UTC metadata on startup.

    The repository module is currently large and central to local persistence. This
    bootstrap keeps schema and timestamp hardening isolated while preserving the
    existing table-creation flow and user data compatibility.
    """
    from job_hunter_agent.infrastructure import repository as repository_module

    repository_class = repository_module.SqliteJobRepository
    if getattr(repository_class, "_schema_migration_bootstrap_installed", False):
        return

    _install_schema_version_registration(repository_class)
    _install_utc_write_normalization(repository_class)
    repository_class._schema_migration_bootstrap_installed = True


def _install_schema_version_registration(repository_class: type[Any]) -> None:
    original_create_tables: Callable[[Any], None] = repository_class._create_tables

    def create_tables_and_register_schema(self: Any) -> None:
        original_create_tables(self)
        with self._connect() as connection:
            ensure_current_schema_version(connection)

    repository_class._create_tables = create_tables_and_register_schema


def _install_utc_write_normalization(repository_class: type[Any]) -> None:
    original_save_new_jobs = repository_class.save_new_jobs
    original_create_application_draft = repository_class.create_application_draft
    original_mark_application_status = repository_class.mark_application_status
    original_record_application_event = repository_class._record_application_event_with_connection
    original_record_job_event = repository_class._record_job_event_with_connection

    def save_new_jobs_with_utc_created_at(self: Any, jobs: list[Any]) -> list[Any]:
        saved_jobs = original_save_new_jobs(self, jobs)
        if not saved_jobs:
            return saved_jobs
        normalized_jobs: list[Any] = []
        with self._connect() as connection:
            for job in saved_jobs:
                created_at = self._utc_now_iso()
                if job.id is not None:
                    connection.execute("UPDATE jobs SET created_at = ? WHERE id = ?", (created_at, job.id))
                normalized_jobs.append(replace(job, created_at=created_at))
        return normalized_jobs

    def remember_seen_job_with_utc(
        self: Any,
        url: str,
        external_key: str,
        source_site: str,
        reason: str,
    ) -> None:
        timestamp = self._utc_now_iso()
        with self._connect() as connection:
            current = connection.execute("SELECT 1 FROM seen_jobs WHERE url = ?", (url,)).fetchone()
            if current is None:
                connection.execute(
                    """
                    INSERT INTO seen_jobs (url, external_key, source_site, reason, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (url, external_key, source_site, reason, timestamp, timestamp),
                )
                return
            connection.execute(
                """
                UPDATE seen_jobs
                SET external_key = ?, source_site = ?, reason = ?, last_seen_at = ?
                WHERE url = ?
                """,
                (external_key, source_site, reason, timestamp, url),
            )

    def record_collection_log_with_utc(
        self: Any,
        source_site: str,
        level: str,
        message: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO collection_logs (source_site, level, message, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (source_site, level, message, self._utc_now_iso()),
            )

    def create_application_draft_with_utc_timestamps(self: Any, job_id: int, *args: Any, **kwargs: Any) -> Any:
        existing = self.get_application_by_job(job_id)
        application = original_create_application_draft(self, job_id, *args, **kwargs)
        if existing is not None:
            return application
        timestamp = self._utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                "UPDATE job_applications SET created_at = ?, updated_at = ? WHERE id = ?",
                (timestamp, timestamp, application.id),
            )
        return replace(application, created_at=timestamp, updated_at=timestamp)

    def mark_application_status_with_utc_updated_at(self: Any, application_id: int, *args: Any, **kwargs: Any) -> None:
        original_mark_application_status(self, application_id, *args, **kwargs)
        with self._connect() as connection:
            connection.execute(
                "UPDATE job_applications SET updated_at = ? WHERE id = ?",
                (self._utc_now_iso(), application_id),
            )

    def update_collection_cursor_with_utc(
        self: Any,
        source_site: str,
        search_url: str,
        next_page: int,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO collection_cursors (source_site, search_url, next_page, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source_site, search_url) DO UPDATE SET
                    next_page = excluded.next_page,
                    updated_at = excluded.updated_at
                """,
                (source_site, search_url, max(1, next_page), self._utc_now_iso()),
            )

    def record_application_event_with_utc_created_at(connection: Any, application_id: int, *args: Any, **kwargs: Any) -> Any:
        event = original_record_application_event(connection, application_id, *args, **kwargs)
        created_at = repository_class._utc_now_iso()
        if event.id is not None:
            connection.execute("UPDATE job_application_events SET created_at = ? WHERE id = ?", (created_at, event.id))
        return replace(event, created_at=created_at)

    def record_job_event_with_utc_created_at(connection: Any, job_id: int, *args: Any, **kwargs: Any) -> Any:
        event = original_record_job_event(connection, job_id, *args, **kwargs)
        created_at = repository_class._utc_now_iso()
        if event.id is not None:
            connection.execute("UPDATE job_status_events SET created_at = ? WHERE id = ?", (created_at, event.id))
        return replace(event, created_at=created_at)

    repository_class.save_new_jobs = save_new_jobs_with_utc_created_at
    repository_class.remember_seen_job = remember_seen_job_with_utc
    repository_class.record_collection_log = record_collection_log_with_utc
    repository_class.create_application_draft = create_application_draft_with_utc_timestamps
    repository_class.mark_application_status = mark_application_status_with_utc_updated_at
    repository_class.update_collection_cursor = update_collection_cursor_with_utc
    repository_class._record_application_event_with_connection = staticmethod(record_application_event_with_utc_created_at)
    repository_class._record_job_event_with_connection = staticmethod(record_job_event_with_utc_created_at)
