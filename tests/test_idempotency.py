from __future__ import annotations

from unittest import TestCase

from job_hunter_agent.core.domain import JobPosting
from job_hunter_agent.core.events import JobCollectedV1, JobScoredV1
from job_hunter_agent.core.idempotency import (
    build_event_processing_key,
    build_event_subject_key,
    build_job_scoring_key,
)


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


class IdempotencyTests(TestCase):
    def test_build_event_subject_key_includes_type_version_and_subject(self) -> None:
        self.assertEqual(
            build_event_subject_key(event_type="JobScoring", event_version=1, subject="run_id=1:external_key=abc"),
            "JobScoring:v1:run_id=1:external_key=abc",
        )

    def test_build_job_scoring_key_is_stable_for_same_run_and_external_key(self) -> None:
        event = JobCollectedV1(run_id=7, jobs=(_job(),), jobs_seen=1, jobs_saved=1, errors=0)

        first = build_job_scoring_key(event=event, external_key="job-key-123")
        second = build_job_scoring_key(event=event, external_key="job-key-123")

        self.assertEqual(first, second)
        self.assertEqual(first, "JobScoring:v1:run_id=7:external_key=job-key-123")

    def test_build_event_processing_key_defaults_to_event_id(self) -> None:
        event = JobScoredV1(
            run_id=7,
            external_key="job-key-123",
            accepted=True,
            relevance=9,
            event_id="evt-1",
        )

        self.assertEqual(
            build_event_processing_key(event=event),
            "JobScoredV1:v1:evt-1",
        )

    def test_build_event_processing_key_accepts_explicit_subject(self) -> None:
        event = JobScoredV1(
            run_id=7,
            external_key="job-key-123",
            accepted=True,
            relevance=9,
            event_id="evt-1",
        )

        self.assertEqual(
            build_event_processing_key(event=event, subject="external_key=job-key-123"),
            "JobScoredV1:v1:external_key=job-key-123",
        )
