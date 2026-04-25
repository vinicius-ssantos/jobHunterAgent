from __future__ import annotations

import shutil
from unittest import TestCase

from job_hunter_agent.core.domain import JobPosting
from job_hunter_agent.core.event_bus import LocalNdjsonEventBus
from job_hunter_agent.core.events import JobCollectedV1, JobScoredV1
from tests.tmp_workspace import prepare_workspace_tmp_dir


def _job() -> JobPosting:
    return JobPosting(
        title="Backend Java",
        company="ACME",
        location="Brasil",
        work_mode="remoto",
        salary_text="Nao informado",
        url="https://www.linkedin.com/jobs/view/123/",
        source_site="LinkedIn",
        summary="Java backend",
        relevance=9,
        rationale="fit",
        external_key="job-key-123",
    )


class LocalNdjsonEventBusTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = prepare_workspace_tmp_dir("event-bus")
        self.events_path = self.temp_dir / "events.ndjson"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_publish_and_read_all_preserves_event_order(self) -> None:
        bus = LocalNdjsonEventBus(self.events_path)
        collected = JobCollectedV1(
            run_id=1,
            jobs=(_job(),),
            jobs_seen=1,
            jobs_saved=1,
            errors=0,
            event_id="evt-collected",
            occurred_at="2026-04-24T12:00:00+00:00",
        )
        scored = JobScoredV1(
            run_id=1,
            external_key="job-key-123",
            accepted=True,
            relevance=9,
            event_id="evt-scored",
            occurred_at="2026-04-24T12:01:00+00:00",
        )

        bus.publish(collected)
        bus.publish(scored)

        events = bus.read_all()

        self.assertEqual(len(events), 2)
        self.assertIsInstance(events[0], JobCollectedV1)
        self.assertIsInstance(events[1], JobScoredV1)
        self.assertEqual(events[0].event_id, "evt-collected")
        self.assertEqual(events[1].event_id, "evt-scored")

    def test_read_helpers_filter_by_event_type(self) -> None:
        bus = LocalNdjsonEventBus(self.events_path)
        bus.publish(
            JobCollectedV1(
                run_id=1,
                jobs=(_job(),),
                jobs_seen=1,
                jobs_saved=1,
                errors=0,
            )
        )
        bus.publish(
            JobScoredV1(
                run_id=1,
                external_key="job-key-123",
                accepted=True,
                relevance=9,
            )
        )

        self.assertEqual(len(bus.read_job_collected()), 1)
        self.assertEqual(len(bus.read_job_scored()), 1)

    def test_read_all_ignores_invalid_lines(self) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self.events_path.write_text(
            "not-json\n"
            "{\"event_type\": \"UnknownEvent\"}\n",
            encoding="utf-8",
        )
        bus = LocalNdjsonEventBus(self.events_path)

        self.assertEqual(bus.read_all(), ())

    def test_read_all_returns_empty_tuple_for_missing_file(self) -> None:
        bus = LocalNdjsonEventBus(self.temp_dir / "missing.ndjson")

        self.assertEqual(bus.read_all(), ())
