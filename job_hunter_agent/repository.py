from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Optional, Protocol

from job_hunter_agent.domain import CollectionRun, JobPosting, VALID_STATUSES


class JobRepository(Protocol):
    def save_new_jobs(self, jobs: list[JobPosting]) -> list[JobPosting]:
        raise NotImplementedError

    def mark_status(self, job_id: int, status: str) -> None:
        raise NotImplementedError

    def list_jobs_by_status(self, status: str) -> list[JobPosting]:
        raise NotImplementedError

    def get_job(self, job_id: int) -> Optional[JobPosting]:
        raise NotImplementedError

    def job_exists(self, url: str, external_key: str) -> bool:
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


class SqliteJobRepository:
    def __init__(self, db_path: str | Path = "jobs.db") -> None:
        self.db_path = Path(db_path)
        self._create_tables()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.db_path)

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

                saved_jobs.append(
                    replace(
                        job,
                        id=cursor.lastrowid,
                        created_at=datetime.now().isoformat(timespec="seconds"),
                    )
                )

        return saved_jobs

    def mark_status(self, job_id: int, status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        with self._connect() as connection:
            connection.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))

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

    def job_exists(self, url: str, external_key: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM jobs WHERE url = ? OR external_key = ?",
                (url, external_key),
            ).fetchone()
        return row is not None

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
            cursor = connection.execute("INSERT INTO collection_runs DEFAULT VALUES")
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
                (datetime.now().isoformat(timespec="seconds"), status, jobs_seen, jobs_saved, errors, run_id),
            )

    def interrupt_running_collection_runs(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE collection_runs
                SET finished_at = ?, status = 'interrupted'
                WHERE status = 'running'
                """,
                (datetime.now().isoformat(timespec="seconds"),),
            )
        return cursor.rowcount

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
