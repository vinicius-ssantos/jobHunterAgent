from __future__ import annotations

import json
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from job_hunter_agent.application.collector_worker import (
    append_event_ndjson,
    build_job_collected_event,
    run_collector_worker_once,
)
from job_hunter_agent.core.domain import CollectionReport, JobPosting
from tests.tmp_workspace import prepare_workspace_tmp_dir


def _sample_job(job_id: int = 1) -> JobPosting:
    return JobPosting(
        id=job_id,
        title="Backend Java",
        company="ACME",
        location="Brasil",
        work_mode="remoto",
        salary_text="Nao informado",
        url=f"https://example.com/{job_id}",
        source_site="LinkedIn",
        summary="Resumo",
        relevance=8,
        rationale="fit",
        external_key=f"key-{job_id}",
    )


class CollectorWorkerSerializationTests(TestCase):
    def test_append_event_ndjson_writes_single_line_json(self) -> None:
        temp_dir = prepare_workspace_tmp_dir("collector-worker-events")
        output_path = temp_dir / "events.ndjson"
        event = build_job_collected_event(
            run_id=10,
            report=CollectionReport(jobs=(_sample_job(),), jobs_seen=1, jobs_saved=1, errors=0),
        )
        try:
            append_event_ndjson(output_path=output_path, event=event)
            lines = output_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["run_id"], 10)
            self.assertEqual(payload["jobs_seen"], 1)
            self.assertEqual(payload["jobs_saved"], 1)
            self.assertEqual(len(payload["jobs"]), 1)
        finally:
            if output_path.exists():
                output_path.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()


class CollectorWorkerExecutionTests(IsolatedAsyncioTestCase):
    async def test_run_collector_worker_once_persists_run_and_emits_event(self) -> None:
        class _Run:
            id = 33

        class _Repository:
            def __init__(self) -> None:
                self.finished: list[tuple[int, str, int, int, int]] = []

            def start_collection_run(self):
                return _Run()

            def finish_collection_run(self, run_id: int, *, status: str, jobs_seen: int, jobs_saved: int, errors: int) -> None:
                self.finished.append((run_id, status, jobs_seen, jobs_saved, errors))

        class _Collector:
            async def collect_new_jobs_report(self):
                return CollectionReport(jobs=(_sample_job(),), jobs_seen=1, jobs_saved=1, errors=0)

        repository = _Repository()
        output_path = Path("logs/test-worker-events.ndjson")

        with patch(
            "job_hunter_agent.application.collector_worker.create_repository",
            return_value=repository,
        ), patch(
            "job_hunter_agent.application.collector_worker.create_collection_service",
            return_value=_Collector(),
        ), patch(
            "job_hunter_agent.application.collector_worker.append_event_ndjson",
        ) as append_mock:
            rendered = await run_collector_worker_once(output_path=output_path, settings=object())

        self.assertIn("JobCollectedV1", rendered)
        self.assertIn("run_id=33", rendered)
        self.assertEqual(repository.finished, [(33, "success", 1, 1, 0)])
        append_mock.assert_called_once()
