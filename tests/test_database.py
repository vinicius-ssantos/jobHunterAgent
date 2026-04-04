import shutil
import unittest

from job_hunter_agent.domain import JobPosting
from job_hunter_agent.repository import SqliteJobRepository
from tests.tmp_workspace import prepare_workspace_tmp_dir


def sample_job(url: str, external_key: str) -> JobPosting:
    return JobPosting(
        title="Senior Kotlin Engineer",
        company="ACME",
        location="Brasil",
        work_mode="remoto",
        salary_text="Nao informado",
        url=url,
        source_site="LinkedIn",
        summary="Resumo",
        relevance=8,
        rationale="Boa aderencia ao perfil.",
        external_key=external_key,
    )


class SqliteJobRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = prepare_workspace_tmp_dir("db")
        self.db_path = self.temp_dir / "jobs.db"
        self.repository = SqliteJobRepository(self.db_path)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_new_jobs_ignores_duplicates(self) -> None:
        first = sample_job("https://example.com/job-1", "key-1")
        duplicate = sample_job("https://example.com/job-1", "key-1")

        saved_first = self.repository.save_new_jobs([first])
        saved_second = self.repository.save_new_jobs([duplicate])

        self.assertEqual(len(saved_first), 1)
        self.assertEqual(len(saved_second), 0)

    def test_save_new_jobs_ignores_duplicate_external_key(self) -> None:
        first = sample_job("https://example.com/job-1", "key-1")
        duplicate_external_key = sample_job("https://example.com/job-2", "key-1")

        saved_first = self.repository.save_new_jobs([first])
        saved_second = self.repository.save_new_jobs([duplicate_external_key])

        self.assertEqual(len(saved_first), 1)
        self.assertEqual(len(saved_second), 0)

    def test_summary_counts_statuses(self) -> None:
        saved = self.repository.save_new_jobs(
            [
                sample_job("https://example.com/job-1", "key-1"),
                sample_job("https://example.com/job-2", "key-2"),
            ]
        )
        self.repository.mark_status(saved[0].id, "approved")
        self.repository.mark_status(saved[1].id, "rejected")

        summary = self.repository.summary()

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["approved"], 1)
        self.assertEqual(summary["rejected"], 1)

    def test_collection_run_is_started_and_finished(self) -> None:
        run = self.repository.start_collection_run()

        self.repository.finish_collection_run(
            run.id,
            status="success",
            jobs_seen=3,
            jobs_saved=2,
            errors=0,
        )

        with self.repository._connect() as connection:
            row = connection.execute(
                """
                SELECT status, jobs_seen, jobs_saved, errors, finished_at
                FROM collection_runs
                WHERE id = ?
                """,
                (run.id,),
            ).fetchone()

        self.assertEqual(row[0], "success")
        self.assertEqual(row[1], 3)
        self.assertEqual(row[2], 2)
        self.assertEqual(row[3], 0)
        self.assertIsNotNone(row[4])

    def test_interrupt_running_collection_runs_marks_stale_runs(self) -> None:
        first = self.repository.start_collection_run()
        second = self.repository.start_collection_run()
        self.repository.finish_collection_run(
            first.id,
            status="success",
            jobs_seen=1,
            jobs_saved=1,
            errors=0,
        )

        interrupted = self.repository.interrupt_running_collection_runs()

        self.assertEqual(interrupted, 1)
        with self.repository._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, status, finished_at
                FROM collection_runs
                ORDER BY id
                """
            ).fetchall()

        self.assertEqual(rows[0][1], "success")
        self.assertEqual(rows[1][1], "interrupted")
        self.assertIsNotNone(rows[1][2])

    def test_mark_status_rejects_invalid_transition_value(self) -> None:
        saved = self.repository.save_new_jobs([sample_job("https://example.com/job-1", "key-1")])

        with self.assertRaises(ValueError):
            self.repository.mark_status(saved[0].id, "archived")

    def test_list_recent_jobs_returns_latest_first(self) -> None:
        self.repository.save_new_jobs(
            [
                sample_job("https://example.com/job-1", "key-1"),
                sample_job("https://example.com/job-2", "key-2"),
            ]
        )

        jobs = self.repository.list_recent_jobs(limit=2)

        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].url, "https://example.com/job-2")
