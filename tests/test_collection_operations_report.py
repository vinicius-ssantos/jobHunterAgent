import shutil
import unittest

from job_hunter_agent.application.collection_operations_report import (
    build_collection_operations_report,
    render_collection_operations_report,
)
from job_hunter_agent.infrastructure.repository import SqliteJobRepository
from tests.tmp_workspace import prepare_workspace_tmp_dir


class CollectionOperationsReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = prepare_workspace_tmp_dir("collection-operations-report")
        self.repository = SqliteJobRepository(self.temp_dir / "jobs.db")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_collection_operations_report_reads_runs_and_logs(self) -> None:
        first = self.repository.start_collection_run()
        self.repository.finish_collection_run(
            first.id,
            status="success",
            jobs_seen=3,
            jobs_saved=2,
            errors=0,
        )
        second = self.repository.start_collection_run()
        self.repository.finish_collection_run(
            second.id,
            status="error",
            jobs_seen=4,
            jobs_saved=1,
            errors=2,
        )
        self.repository.record_collection_log("LinkedIn", "info", "coleta iniciada")
        self.repository.record_collection_log("LinkedIn", "error", "falha temporaria")

        report = build_collection_operations_report(self.repository, since="2000-01-01T00:00:00+00:00")
        rendered = render_collection_operations_report(report)

        self.assertEqual(report.run_summary.total_runs, 2)
        self.assertEqual(report.run_summary.success_runs, 1)
        self.assertEqual(report.run_summary.error_runs, 1)
        self.assertEqual(report.run_summary.jobs_seen, 7)
        self.assertEqual(report.run_summary.jobs_saved, 3)
        self.assertEqual(report.run_summary.errors, 2)
        self.assertEqual(report.log_summary.by_source, {"LinkedIn": 2})
        self.assertEqual(report.log_summary.by_level, {"error": 1, "info": 1})
        self.assertIn("coleta:", rendered)
        self.assertIn("- ciclos=2", rendered)
        self.assertIn("- LinkedIn=2", rendered)
        self.assertIn("falha temporaria", rendered)

    def test_build_collection_operations_report_handles_non_sqlite_repository(self) -> None:
        report = build_collection_operations_report(object(), since="2000-01-01T00:00:00+00:00")
        rendered = render_collection_operations_report(report)

        self.assertEqual(report.run_summary.total_runs, 0)
        self.assertIn("- ciclos=0", rendered)
        self.assertIn("- jobs_saved=0", rendered)
