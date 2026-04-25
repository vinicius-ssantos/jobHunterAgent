from __future__ import annotations

from unittest import TestCase

from job_hunter_agent.core.domain import JobPosting
from job_hunter_agent.core.events import (
    JobCollectedV1,
    JobScoredV1,
    event_from_dict,
    event_from_json,
    event_to_dict,
    event_to_json,
)


def _job() -> JobPosting:
    return JobPosting(
        id=123,
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
        status="collected",
        created_at="2026-04-24T12:00:00+00:00",
    )


class EventContractTests(TestCase):
    def test_job_collected_round_trip_json_preserves_payload_and_metadata(self) -> None:
        event = JobCollectedV1(
            run_id=7,
            jobs=(_job(),),
            jobs_seen=2,
            jobs_saved=1,
            errors=0,
            event_id="evt-1",
            occurred_at="2026-04-24T12:00:00+00:00",
            correlation_id="collection-run:7",
        )

        decoded = event_from_json(event_to_json(event))

        self.assertIsInstance(decoded, JobCollectedV1)
        self.assertEqual(decoded.event_type, "JobCollectedV1")
        self.assertEqual(decoded.event_version, 1)
        self.assertEqual(decoded.event_id, "evt-1")
        self.assertEqual(decoded.correlation_id, "collection-run:7")
        self.assertEqual(decoded.run_id, 7)
        self.assertEqual(decoded.jobs_saved, 1)
        self.assertEqual(decoded.jobs[0].external_key, "job-key-123")

    def test_job_scored_round_trip_json_preserves_payload_and_metadata(self) -> None:
        event = JobScoredV1(
            run_id=7,
            external_key="job-key-123",
            accepted=True,
            relevance=9,
            event_id="evt-2",
            occurred_at="2026-04-24T12:01:00+00:00",
            correlation_id="collection-run:7",
        )

        decoded = event_from_json(event_to_json(event))

        self.assertIsInstance(decoded, JobScoredV1)
        self.assertEqual(decoded.event_type, "JobScoredV1")
        self.assertEqual(decoded.event_version, 1)
        self.assertEqual(decoded.event_id, "evt-2")
        self.assertEqual(decoded.correlation_id, "collection-run:7")
        self.assertEqual(decoded.external_key, "job-key-123")
        self.assertTrue(decoded.accepted)
        self.assertEqual(decoded.relevance, 9)

    def test_job_collected_accepts_legacy_payload_without_event_metadata(self) -> None:
        legacy_payload = {
            "run_id": 7,
            "jobs": [event_to_dict(JobCollectedV1(run_id=7, jobs=(_job(),), jobs_seen=1, jobs_saved=1, errors=0))["jobs"][0]],
            "jobs_seen": 1,
            "jobs_saved": 1,
            "errors": 0,
        }

        decoded = event_from_dict(legacy_payload)

        self.assertIsInstance(decoded, JobCollectedV1)
        self.assertEqual(decoded.event_type, "JobCollectedV1")
        self.assertEqual(decoded.event_version, 1)
        self.assertTrue(decoded.event_id)
        self.assertEqual(decoded.jobs[0].title, "Backend Java")

    def test_job_scored_accepts_legacy_payload_without_event_metadata(self) -> None:
        decoded = event_from_dict(
            {
                "run_id": 7,
                "external_key": "job-key-123",
                "accepted": True,
                "relevance": 9,
            }
        )

        self.assertIsInstance(decoded, JobScoredV1)
        self.assertEqual(decoded.event_type, "JobScoredV1")
        self.assertEqual(decoded.event_version, 1)
        self.assertTrue(decoded.event_id)
        self.assertEqual(decoded.external_key, "job-key-123")
