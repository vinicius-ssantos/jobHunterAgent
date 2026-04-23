from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Protocol

from job_hunter_agent.core.domain import (
    CollectionRun,
    JobApplication,
    JobApplicationEvent,
    JobStatusEvent,
    JobPosting,
    VALID_APPLICATION_STATUSES,
    VALID_APPLICATION_SUPPORT_LEVELS,
    VALID_STATUSES,
)
from job_hunter_agent.core.job_identity import JobIdentityStrategy, PortalAwareJobIdentityStrategy


class JobRepository(Protocol):
    def save_new_jobs(self, jobs: list[JobPosting]) -> list[JobPosting]:
        raise NotImplementedError

    def mark_status(self, job_id: int, status: str, *, detail: str = "") -> None:
        raise NotImplementedError

    def list_jobs_by_status(self, status: str) -> list[JobPosting]:
        raise NotImplementedError

    def get_job(self, job_id: int) -> Optional[JobPosting]:
        raise NotImplementedError

    def list_job_events(self, job_id: int, *, limit: Optional[int] = None) -> list[JobStatusEvent]:
        raise NotImplementedError

    def job_exists(self, url: str, external_key: str) -> bool:
        raise NotImplementedError

    def job_url_exists(self, url: str) -> bool:
        raise NotImplementedError

    def seen_job_exists(self, url: str, external_key: str) -> bool:
        raise NotImplementedError

    def seen_job_url_exists(self, url: str) -> bool:
        raise NotImplementedError

    def remember_seen_job(self, url: str, external_key: str, source_site: str, reason: str) -> None:
        raise NotImplementedError

    def summary(self) -> dict[str, int]:
        raise NotImplementedError

    def record_collection_log(self, source_site: str, level: str, message: str) -> None:
        raise NotImplementedError

    def list_recent_jobs(self, limit: int = 10) -> list[JobPosting]:
        raise NotImplementedError

    def start_collection_run(self) -> CollectionRun:
        raise NotImplementedError

    def finish_collection_run(
        self,
        run_id: int,
        *,
        status: str,
        jobs_seen: int,
        jobs_saved: int,
        errors: int,
    ) -> None:
        raise NotImplementedError

    def interrupt_running_collection_runs(self) -> int:
        raise NotImplementedError

    def create_application_draft(
        self,
        job_id: int,
        notes: str = "",
        *,
        support_level: str = "manual_review",
        support_rationale: str = "",
    ) -> JobApplication:
        raise NotImplementedError

    def get_application_by_job(self, job_id: int) -> Optional[JobApplication]:
        raise NotImplementedError

    def get_application(self, application_id: int) -> Optional[JobApplication]:
        raise NotImplementedError

    def mark_application_status(
        self,
        application_id: int,
        *,
        status: str,
        event_detail: str = "",
        notes: Optional[str] = None,
        last_preflight_detail: Optional[str] = None,
        last_submit_detail: Optional[str] = None,
        last_error: Optional[str] = None,
        submitted_at: Optional[str] = None,
    ) -> None:
        raise NotImplementedError

    def list_applications_by_status(self, status: str) -> list[JobApplication]:
        raise NotImplementedError

    def list_applications_with_jobs_by_status(self, status: str) -> list[tuple[JobApplication, Optional[JobPosting]]]:
        raise NotImplementedError

    def list_tracked_applications_with_jobs(self) -> list[tuple[JobApplication, Optional[JobPosting]]]:
        raise NotImplementedError

    def application_summary(self) -> dict[str, int]:
        raise NotImplementedError

    def record_application_event(
        self,
        application_id: int,
        *,
        event_type: str,
        detail: str = "",
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
    ) -> JobApplicationEvent:
        raise NotImplementedError

    def list_application_events(
        self,
        application_id: int,
        *,
        limit: Optional[int] = None,
    ) -> list[JobApplicationEvent]:
        raise NotImplementedError

    def list_recent_application_events_since(self, since: str) -> list[JobApplicationEvent]:
        raise NotImplementedError

    def count_submitted_applications_since(self, since: str) -> int:
        raise NotImplementedError

    def get_collection_cursor(self, source_site: str, search_url: str) -> int:
        raise NotImplementedError

    def update_collection_cursor(self, source_site: str, search_url: str, next_page: int) -> None:
        raise NotImplementedError


class SqliteJobRepository:
    def __init__(
        self,
        db_path: str | Path = "jobs.db",
        *,
        identity_strategy: JobIdentityStrategy | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.identity_strategy = identity_strategy or PortalAwareJobIdentityStrategy()
        self._create_tables()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.db_path)

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _url_lookup_patterns(self, url: str) -> list[str]:
        return self.identity_strategy.url_lookup_patterns(url)

    def _create_tables(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT,
                    work_mode TEXT,
                    salary_text TEXT,
                    url TEXT NOT NULL UNIQUE,
                    source_site TEXT NOT NULL,
                    summary TEXT,
                    relevance INTEGER NOT NULL,
                    rationale TEXT NOT NULL,
                    external_key TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'collected',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_site TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    finished_at TEXT,
                    status TEXT NOT NULL DEFAULT 'running',
                    jobs_seen INTEGER NOT NULL DEFAULT 0,
                    jobs_saved INTEGER NOT NULL DEFAULT 0,
                    errors INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    external_key TEXT NOT NULL,
                    source_site TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'draft',
                    support_level TEXT NOT NULL DEFAULT 'manual_review',
                    support_rationale TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    last_preflight_detail TEXT NOT NULL DEFAULT '',
                    last_submit_detail TEXT NOT NULL DEFAULT '',
                    last_error TEXT NOT NULL DEFAULT '',
                    submitted_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES jobs(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_application_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    from_status TEXT,
                    to_status TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (application_id) REFERENCES job_applications(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_status_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    from_status TEXT,
                    to_status TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES jobs(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_cursors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_site TEXT NOT NULL,
                    search_url TEXT NOT NULL,
                    next_page INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_site, search_url)
                )
                """
            )
            self._ensure_job_applications_columns(connection)

    @staticmethod
    def _ensure_job_applications_columns(connection: sqlite3.Connection) -> None:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(job_applications)").fetchall()
        }
        if "support_level" not in columns:
            connection.execute(
                "ALTER TABLE job_applications ADD COLUMN support_level TEXT NOT NULL DEFAULT 'manual_review'"
            )
        if "support_rationale" not in columns:
            connection.execute(
                "ALTER TABLE job_applications ADD COLUMN support_rationale TEXT NOT NULL DEFAULT ''"
            )
        if "last_preflight_detail" not in columns:
            connection.execute(
                "ALTER TABLE job_applications ADD COLUMN last_preflight_detail TEXT NOT NULL DEFAULT ''"
            )
        if "last_submit_detail" not in columns:
            connection.execute(
                "ALTER TABLE job_applications ADD COLUMN last_submit_detail TEXT NOT NULL DEFAULT ''"
            )

    def save_new_jobs(self, jobs: list[JobPosting]) -> list[JobPosting]:
        saved_jobs: list[JobPosting] = []
        with self._connect() as connection:
            for job in jobs:
                if self.job_exists(job.url, job.external_key):
                    continue
                try:
                    cursor = connection.execute(
                        """
                        INSERT INTO jobs (
                            title, company, location, work_mode, salary_text, url,
                            source_site, summary, relevance, rationale, external_key, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            job.title,
                            job.company,
                            job.location,
                            job.work_mode,
                            job.salary_text,
                            job.url,
                            job.source_site,
                            job.summary,
                            job.relevance,
                            job.rationale,
                            job.external_key,
                            job.status,
                        ),
                    )
                except sqlite3.IntegrityError:
                    continue

                saved_job = replace(
                    job,
                    id=cursor.lastrowid,
                    created_at=datetime.now().isoformat(timespec="seconds"),
                )
                self._record_job_event_with_connection(
                    connection,
                    saved_job.id,
                    event_type="job_collected",
                    detail="vaga coletada e persistida localmente",
                    to_status=saved_job.status,
                )
                saved_jobs.append(saved_job)

        return saved_jobs

    def mark_status(self, job_id: int, status: str, *, detail: str = "") -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        with self._connect() as connection:
            current = connection.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if current is None:
                raise ValueError(f"Job not found: {job_id}")
            previous_status = current[0]
            connection.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
            self._record_job_event_with_connection(
                connection,
                job_id,
                event_type="status_changed" if previous_status != status else "status_reaffirmed",
                detail=detail,
                from_status=previous_status,
                to_status=status,
            )

    def list_jobs_by_status(self, status: str) -> list[JobPosting]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, company, location, work_mode, salary_text, url,
                       source_site, summary, relevance, rationale, external_key, status, created_at
                FROM jobs
                WHERE status = ?
                ORDER BY relevance DESC, created_at DESC
                """,
                (status,),
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def get_job(self, job_id: int) -> Optional[JobPosting]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, title, company, location, work_mode, salary_text, url,
                       source_site, summary, relevance, rationale, external_key, status, created_at
                FROM jobs
                WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
        return self._row_to_job(row) if row else None

    def list_job_events(self, job_id: int, *, limit: Optional[int] = None) -> list[JobStatusEvent]:
        query = """
            SELECT id, job_id, event_type, detail, from_status, to_status, created_at
            FROM job_status_events
            WHERE job_id = ?
            ORDER BY id DESC
        """
        params: tuple[object, ...]
        if limit is None:
            params = (job_id,)
        else:
            query += "\nLIMIT ?"
            params = (job_id, limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_job_event(row) for row in rows]

    def job_exists(self, url: str, external_key: str) -> bool:
        with self._connect() as connection:
            patterns = self._url_lookup_patterns(url)
            if len(patterns) > 1:
                row = connection.execute(
                    "SELECT 1 FROM jobs WHERE url = ? OR url LIKE ? OR external_key = ?",
                    (patterns[0], patterns[1], external_key),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT 1 FROM jobs WHERE url = ? OR external_key = ?",
                    (url, external_key),
                ).fetchone()
        return row is not None

    def job_url_exists(self, url: str) -> bool:
        with self._connect() as connection:
            patterns = self._url_lookup_patterns(url)
            if len(patterns) > 1:
                row = connection.execute(
                    "SELECT 1 FROM jobs WHERE url = ? OR url LIKE ?",
                    (patterns[0], patterns[1]),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT 1 FROM jobs WHERE url = ?",
                    (url,),
                ).fetchone()
        return row is not None

    def seen_job_exists(self, url: str, external_key: str) -> bool:
        with self._connect() as connection:
            patterns = self._url_lookup_patterns(url)
            if len(patterns) > 1:
                row = connection.execute(
                    "SELECT 1 FROM seen_jobs WHERE url = ? OR url LIKE ? OR external_key = ?",
                    (patterns[0], patterns[1], external_key),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT 1 FROM seen_jobs WHERE url = ? OR external_key = ?",
                    (url, external_key),
                ).fetchone()
        return row is not None

    def seen_job_url_exists(self, url: str) -> bool:
        with self._connect() as connection:
            patterns = self._url_lookup_patterns(url)
            if len(patterns) > 1:
                row = connection.execute(
                    "SELECT 1 FROM seen_jobs WHERE url = ? OR url LIKE ?",
                    (patterns[0], patterns[1]),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT 1 FROM seen_jobs WHERE url = ?",
                    (url,),
                ).fetchone()
        return row is not None

    def remember_seen_job(self, url: str, external_key: str, source_site: str, reason: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO seen_jobs (url, external_key, source_site, reason)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    external_key = excluded.external_key,
                    source_site = excluded.source_site,
                    reason = excluded.reason,
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                (url, external_key, source_site, reason),
            )

    def summary(self) -> dict[str, int]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'collected' THEN 1 ELSE 0 END) AS collected,
                    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS approved,
                    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected,
                    SUM(CASE WHEN status = 'error_collect' THEN 1 ELSE 0 END) AS error_collect
                FROM jobs
                """
            ).fetchone()
        return {
            "total": row[0] or 0,
            "collected": row[1] or 0,
            "approved": row[2] or 0,
            "rejected": row[3] or 0,
            "error_collect": row[4] or 0,
        }

    def record_collection_log(self, source_site: str, level: str, message: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO collection_logs (source_site, level, message) VALUES (?, ?, ?)",
                (source_site, level, message),
            )

    def list_recent_jobs(self, limit: int = 10) -> list[JobPosting]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, company, location, work_mode, salary_text, url,
                       source_site, summary, relevance, rationale, external_key, status, created_at
                FROM jobs
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def start_collection_run(self) -> CollectionRun:
        with self._connect() as connection:
            started_at = self._utc_now_iso()
            cursor = connection.execute(
                "INSERT INTO collection_runs (started_at, status, jobs_seen, jobs_saved, errors) VALUES (?, 'running', 0, 0, 0)",
                (started_at,),
            )
            row = connection.execute(
                """
                SELECT id, started_at, finished_at, status, jobs_seen, jobs_saved, errors
                FROM collection_runs
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        return self._row_to_collection_run(row)

    def finish_collection_run(
        self,
        run_id: int,
        *,
        status: str,
        jobs_seen: int,
        jobs_saved: int,
        errors: int,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE collection_runs
                SET finished_at = ?, status = ?, jobs_seen = ?, jobs_saved = ?, errors = ?
                WHERE id = ?
                """,
                (self._utc_now_iso(), status, jobs_seen, jobs_saved, errors, run_id),
            )

    def interrupt_running_collection_runs(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE collection_runs
                SET finished_at = ?, status = 'interrupted'
                WHERE status = 'running'
                """,
                (self._utc_now_iso(),),
            )
        return cursor.rowcount

    def create_application_draft(
        self,
        job_id: int,
        notes: str = "",
        *,
        support_level: str = "manual_review",
        support_rationale: str = "",
    ) -> JobApplication:
        if not self.get_job(job_id):
            raise ValueError(f"Job not found: {job_id}")
        if support_level not in VALID_APPLICATION_SUPPORT_LEVELS:
            raise ValueError(f"Invalid application support level: {support_level}")
        existing = self.get_application_by_job(job_id)
        if existing:
            return existing
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO job_applications (job_id, status, support_level, support_rationale, notes)
                VALUES (?, 'draft', ?, ?, ?)
                """,
                (job_id, support_level, support_rationale, notes),
            )
            self._record_application_event_with_connection(
                connection,
                cursor.lastrowid,
                event_type="draft_created",
                detail="rascunho de candidatura criado",
                to_status="draft",
            )
            row = connection.execute(
                """
                SELECT id, job_id, status, support_level, support_rationale, notes,
                       last_preflight_detail, last_submit_detail, last_error, created_at, updated_at, submitted_at
                FROM job_applications
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        return self._row_to_application(row)

    def get_application_by_job(self, job_id: int) -> Optional[JobApplication]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, job_id, status, support_level, support_rationale, notes,
                       last_preflight_detail, last_submit_detail, last_error, created_at, updated_at, submitted_at
                FROM job_applications
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
        return self._row_to_application(row) if row else None

    def get_application(self, application_id: int) -> Optional[JobApplication]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, job_id, status, support_level, support_rationale, notes,
                       last_preflight_detail, last_submit_detail, last_error, created_at, updated_at, submitted_at
                FROM job_applications
                WHERE id = ?
                """,
                (application_id,),
            ).fetchone()
        return self._row_to_application(row) if row else None

    def mark_application_status(
        self,
        application_id: int,
        *,
        status: str,
        event_detail: str = "",
        notes: Optional[str] = None,
        last_preflight_detail: Optional[str] = None,
        last_submit_detail: Optional[str] = None,
        last_error: Optional[str] = None,
        submitted_at: Optional[str] = None,
    ) -> None:
        if status not in VALID_APPLICATION_STATUSES:
            raise ValueError(f"Invalid application status: {status}")
        with self._connect() as connection:
            current = connection.execute(
                """
                SELECT status, notes, last_preflight_detail, last_submit_detail, last_error, submitted_at
                FROM job_applications
                WHERE id = ?
                """,
                (application_id,),
            ).fetchone()
            if current is None:
                raise ValueError(f"Application not found: {application_id}")
            previous_status = current[0]
            resolved_notes = current[1] if notes is None else notes
            resolved_preflight = current[2] if last_preflight_detail is None else last_preflight_detail
            resolved_submit = current[3] if last_submit_detail is None else last_submit_detail
            resolved_error = current[4] if last_error is None else last_error
            resolved_submitted_at = current[5] if submitted_at is None else submitted_at
            connection.execute(
                """
                UPDATE job_applications
                SET status = ?, notes = ?, last_preflight_detail = ?, last_submit_detail = ?, last_error = ?, submitted_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    resolved_notes,
                    resolved_preflight,
                    resolved_submit,
                    resolved_error,
                    resolved_submitted_at,
                    datetime.now().isoformat(timespec="seconds"),
                    application_id,
                ),
            )
            self._record_application_event_with_connection(
                connection,
                application_id,
                event_type="status_changed" if previous_status != status else "status_reaffirmed",
                detail=event_detail,
                from_status=previous_status,
                to_status=status,
            )

    def list_applications_by_status(self, status: str) -> list[JobApplication]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, job_id, status, support_level, support_rationale, notes,
                       last_preflight_detail, last_submit_detail, last_error, created_at, updated_at, submitted_at
                FROM job_applications
                WHERE status = ?
                ORDER BY updated_at DESC, id DESC
                """,
                (status,),
            ).fetchall()
        return [self._row_to_application(row) for row in rows]

    def list_applications_with_jobs_by_status(self, status: str) -> list[tuple[JobApplication, Optional[JobPosting]]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    a.id, a.job_id, a.status, a.support_level, a.support_rationale, a.notes,
                    a.last_preflight_detail, a.last_submit_detail, a.last_error, a.created_at, a.updated_at, a.submitted_at,
                    j.id, j.title, j.company, j.location, j.work_mode, j.salary_text, j.url,
                    j.source_site, j.summary, j.relevance, j.rationale, j.external_key, j.status, j.created_at
                FROM job_applications a
                LEFT JOIN jobs j ON j.id = a.job_id
                WHERE a.status = ?
                ORDER BY a.updated_at DESC, a.id DESC
                """,
                (status,),
            ).fetchall()
        return [self._row_to_application_with_job(row) for row in rows]

    def list_tracked_applications_with_jobs(self) -> list[tuple[JobApplication, Optional[JobPosting]]]:
        tracked_statuses = ("draft", "ready_for_review", "confirmed", "authorized_submit", "error_submit", "submitted")
        placeholders = ", ".join("?" for _ in tracked_statuses)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    a.id, a.job_id, a.status, a.support_level, a.support_rationale, a.notes,
                    a.last_preflight_detail, a.last_submit_detail, a.last_error, a.created_at, a.updated_at, a.submitted_at,
                    j.id, j.title, j.company, j.location, j.work_mode, j.salary_text, j.url,
                    j.source_site, j.summary, j.relevance, j.rationale, j.external_key, j.status, j.created_at
                FROM job_applications a
                LEFT JOIN jobs j ON j.id = a.job_id
                WHERE a.status IN ({placeholders})
                ORDER BY a.updated_at DESC, a.id DESC
                """,
                tracked_statuses,
            ).fetchall()
        return [self._row_to_application_with_job(row) for row in rows]

    def application_summary(self) -> dict[str, int]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) AS draft,
                    SUM(CASE WHEN status = 'ready_for_review' THEN 1 ELSE 0 END) AS ready_for_review,
                    SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) AS confirmed,
                    SUM(CASE WHEN status = 'authorized_submit' THEN 1 ELSE 0 END) AS authorized_submit,
                    SUM(CASE WHEN status = 'submitted' THEN 1 ELSE 0 END) AS submitted,
                    SUM(CASE WHEN status = 'error_submit' THEN 1 ELSE 0 END) AS error_submit,
                    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
                FROM job_applications
                """
            ).fetchone()
        return {
            "total": row[0] or 0,
            "draft": row[1] or 0,
            "ready_for_review": row[2] or 0,
            "confirmed": row[3] or 0,
            "authorized_submit": row[4] or 0,
            "submitted": row[5] or 0,
            "error_submit": row[6] or 0,
            "cancelled": row[7] or 0,
        }

    def record_application_event(
        self,
        application_id: int,
        *,
        event_type: str,
        detail: str = "",
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
    ) -> JobApplicationEvent:
        with self._connect() as connection:
            return self._record_application_event_with_connection(
                connection,
                application_id,
                event_type=event_type,
                detail=detail,
                from_status=from_status,
                to_status=to_status,
            )

    def list_application_events(
        self,
        application_id: int,
        *,
        limit: Optional[int] = None,
    ) -> list[JobApplicationEvent]:
        query = """
            SELECT id, application_id, event_type, detail, from_status, to_status, created_at
            FROM job_application_events
            WHERE application_id = ?
            ORDER BY id DESC
        """
        params: tuple[object, ...]
        if limit is None:
            params = (application_id,)
        else:
            query += "\nLIMIT ?"
            params = (application_id, limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_application_event(row) for row in rows]

    def list_recent_application_events_since(self, since: str) -> list[JobApplicationEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, application_id, event_type, detail, from_status, to_status, created_at
                FROM job_application_events
                WHERE created_at >= ?
                ORDER BY id ASC
                """,
                (since,),
            ).fetchall()
        return [self._row_to_application_event(row) for row in rows]

    def count_submitted_applications_since(self, since: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(1)
                FROM job_applications
                WHERE status = 'submitted'
                  AND submitted_at IS NOT NULL
                  AND submitted_at >= ?
                """,
                (since,),
            ).fetchone()
        return int((row[0] if row else 0) or 0)

    def get_collection_cursor(self, source_site: str, search_url: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT next_page
                FROM collection_cursors
                WHERE source_site = ? AND search_url = ?
                """,
                (source_site, search_url),
            ).fetchone()
        if not row:
            return 1
        return max(1, int(row[0]))

    def update_collection_cursor(self, source_site: str, search_url: str, next_page: int) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO collection_cursors (source_site, search_url, next_page, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source_site, search_url) DO UPDATE SET
                    next_page = excluded.next_page,
                    updated_at = excluded.updated_at
                """,
                (
                    source_site,
                    search_url,
                    max(1, next_page),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

    @staticmethod
    def _record_application_event_with_connection(
        connection: sqlite3.Connection,
        application_id: int,
        *,
        event_type: str,
        detail: str = "",
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
    ) -> JobApplicationEvent:
        exists = connection.execute(
            "SELECT 1 FROM job_applications WHERE id = ?",
            (application_id,),
        ).fetchone()
        if exists is None:
            raise ValueError(f"Application not found: {application_id}")
        cursor = connection.execute(
            """
            INSERT INTO job_application_events (application_id, event_type, detail, from_status, to_status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (application_id, event_type, detail, from_status, to_status),
        )
        row = connection.execute(
            """
            SELECT id, application_id, event_type, detail, from_status, to_status, created_at
            FROM job_application_events
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()
        return SqliteJobRepository._row_to_application_event(row)

    @staticmethod
    def _record_job_event_with_connection(
        connection: sqlite3.Connection,
        job_id: int,
        *,
        event_type: str,
        detail: str = "",
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
    ) -> JobStatusEvent:
        exists = connection.execute(
            "SELECT 1 FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if exists is None:
            raise ValueError(f"Job not found: {job_id}")
        cursor = connection.execute(
            """
            INSERT INTO job_status_events (job_id, event_type, detail, from_status, to_status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, event_type, detail, from_status, to_status),
        )
        row = connection.execute(
            """
            SELECT id, job_id, event_type, detail, from_status, to_status, created_at
            FROM job_status_events
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()
        return SqliteJobRepository._row_to_job_event(row)

    @staticmethod
    def _row_to_job(row: tuple) -> JobPosting:
        return JobPosting(
            id=row[0],
            title=row[1],
            company=row[2],
            location=row[3],
            work_mode=row[4],
            salary_text=row[5],
            url=row[6],
            source_site=row[7],
            summary=row[8],
            relevance=row[9],
            rationale=row[10],
            external_key=row[11],
            status=row[12],
            created_at=row[13],
        )

    @staticmethod
    def _row_to_collection_run(row: tuple) -> CollectionRun:
        return CollectionRun(
            id=row[0],
            started_at=row[1],
            finished_at=row[2],
            status=row[3],
            jobs_seen=row[4],
            jobs_saved=row[5],
            errors=row[6],
        )

    @staticmethod
    def _row_to_application(row: tuple) -> JobApplication:
        return JobApplication(
            id=row[0],
            job_id=row[1],
            status=row[2],
            support_level=row[3],
            support_rationale=row[4],
            notes=row[5],
            last_preflight_detail=row[6],
            last_submit_detail=row[7],
            last_error=row[8],
            created_at=row[9],
            updated_at=row[10],
            submitted_at=row[11],
        )

    @staticmethod
    def _row_to_application_event(row: tuple) -> JobApplicationEvent:
        return JobApplicationEvent(
            id=row[0],
            application_id=row[1],
            event_type=row[2],
            detail=row[3],
            from_status=row[4],
            to_status=row[5],
            created_at=row[6],
        )

    @classmethod
    def _row_to_application_with_job(cls, row: tuple) -> tuple[JobApplication, Optional[JobPosting]]:
        application = cls._row_to_application(row[:12])
        if row[12] is None:
            return application, None
        return application, cls._row_to_job(row[12:])

    @staticmethod
    def _row_to_job_event(row: tuple) -> JobStatusEvent:
        return JobStatusEvent(
            id=row[0],
            job_id=row[1],
            event_type=row[2],
            detail=row[3],
            from_status=row[4],
            to_status=row[5],
            created_at=row[6],
        )
