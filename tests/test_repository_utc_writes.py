import shutil
from unittest import TestCase

from job_hunter_agent.core.domain import JobPosting
from job_hunter_agent.infrastructure.repository import SqliteJobRepository
from tests.tmp_workspace import prepare_workspace_tmp_dir


def _sample_job(url: str = "https://example.com/job-1", external_key: str = "key-1") -> JobPosting:
    return JobPosting(
        title="Backend Java",
        company="ACME",
        location="Brasil",
        work_mode="remoto",
        salary_text="Nao informado",
        url=url,
        source_site="LinkedIn",
        summary="Resumo",
        relevance=8,
        rationale="Boa aderencia",
        external_key=external_key,
    )


def _assert_utc(testcase: TestCase, timestamp: str) -> None:
    testcase.assertIn("T", timestamp)
    testcase.assertTrue(timestamp.endswith("+00:00"), timestamp)


class RepositoryUtcWritesTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = prepare_workspace_tmp_dir("utc-writes")
        self.db_path = self.temp_dir / "jobs.db"
        self.repository = SqliteJobRepository(self.db_path)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_job_and_job_event_writes_use_utc_timestamps(self) -> None:
        saved = self.repository.save_new_jobs([_sample_job()])[0]
        events = self.repository.list_job_events(saved.id)

        _assert_utc(self, saved.created_at)
        _assert_utc(self, events[0].created_at)

    def test_seen_job_writes_use_utc_timestamps(self) -> None:
        self.repository.remember_seen_job("https://example.com/job-1", "key-1", "LinkedIn", "first")
        self.repository.remember_seen_job("https://example.com/job-1", "key-1", "LinkedIn", "updated")

        with self.repository._connect() as connection:
            row = connection.execute(
                "SELECT first_seen_at, last_seen_at FROM seen_jobs WHERE url = ?",
                ("https://example.com/job-1",),
            ).fetchone()

        _assert_utc(self, row[0])
        _assert_utc(self, row[1])

    def test_collection_log_and_cursor_writes_use_utc_timestamps(self) -> None:
        self.repository.record_collection_log("LinkedIn", "INFO", "coleta iniciada")
        self.repository.update_collection_cursor("LinkedIn", "https://example.com/search", 2)

        with self.repository._connect() as connection:
            log_row = connection.execute("SELECT created_at FROM collection_logs").fetchone()
            cursor_row = connection.execute("SELECT updated_at FROM collection_cursors").fetchone()

        _assert_utc(self, log_row[0])
        _assert_utc(self, cursor_row[0])

    def test_application_and_application_event_writes_use_utc_timestamps(self) -> None:
        job = self.repository.save_new_jobs([_sample_job()])[0]
        application = self.repository.create_application_draft(job.id)
        self.repository.mark_application_status(application.id, status="ready_for_review")

        stored = self.repository.get_application(application.id)
        events = self.repository.list_application_events(application.id)

        _assert_utc(self, stored.created_at)
        _assert_utc(self, stored.updated_at)
        self.assertGreaterEqual(len(events), 2)
        for event in events:
            _assert_utc(self, event.created_at)
