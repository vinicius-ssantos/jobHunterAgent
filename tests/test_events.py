from __future__ import annotations

from unittest import TestCase

from job_hunter_agent.core.domain import JobPosting
from job_hunter_agent.core.events import (
    ApplicationAuthorizedV1,
    ApplicationBlockedV1,
    ApplicationSubmittedV1,
    JobCollectedV1,
    JobReviewRequestedV1,
    JobReviewedV1,
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

    def test_job_review_requested_round_trip_json_preserves_payload_and_metadata(self) -> None:
        event = JobReviewRequestedV1(
            job_id=123,
            external_key="job-key-123",
            source_site="LinkedIn",
            relevance=9,
            reason="accepted_by_matching",
            event_id="evt-review-requested",
            occurred_at="2026-04-24T12:02:00+00:00",
            correlation_id="collection-run:7",
        )

        decoded = event_from_json(event_to_json(event))

        self.assertIsInstance(decoded, JobReviewRequestedV1)
        self.assertEqual(decoded.event_type, "JobReviewRequestedV1")
        self.assertEqual(decoded.event_version, 1)
        self.assertEqual(decoded.event_id, "evt-review-requested")
        self.assertEqual(decoded.job_id, 123)
        self.assertEqual(decoded.external_key, "job-key-123")
        self.assertEqual(decoded.source_site, "LinkedIn")
        self.assertEqual(decoded.relevance, 9)
        self.assertEqual(decoded.reason, "accepted_by_matching")
        self.assertEqual(decoded.correlation_id, "collection-run:7")

    def test_job_reviewed_round_trip_json_preserves_payload_and_metadata(self) -> None:
        event = JobReviewedV1(
            job_id=123,
            decision="approve",
            status="approved",
            reviewed_by="telegram",
            notes="boa vaga",
            external_key="job-key-123",
            event_id="evt-reviewed",
            occurred_at="2026-04-24T12:03:00+00:00",
            correlation_id="collection-run:7",
        )

        decoded = event_from_json(event_to_json(event))

        self.assertIsInstance(decoded, JobReviewedV1)
        self.assertEqual(decoded.event_type, "JobReviewedV1")
        self.assertEqual(decoded.job_id, 123)
        self.assertEqual(decoded.decision, "approve")
        self.assertEqual(decoded.status, "approved")
        self.assertEqual(decoded.reviewed_by, "telegram")
        self.assertEqual(decoded.notes, "boa vaga")
        self.assertEqual(decoded.external_key, "job-key-123")

    def test_application_authorized_round_trip_json_preserves_payload_and_metadata(self) -> None:
        event = ApplicationAuthorizedV1(
            application_id=55,
            job_id=123,
            authorized_by="cli",
            authorization_source="manual",
            event_id="evt-authorized",
            occurred_at="2026-04-24T12:04:00+00:00",
            correlation_id="application:55",
        )

        decoded = event_from_json(event_to_json(event))

        self.assertIsInstance(decoded, ApplicationAuthorizedV1)
        self.assertEqual(decoded.event_type, "ApplicationAuthorizedV1")
        self.assertEqual(decoded.application_id, 55)
        self.assertEqual(decoded.job_id, 123)
        self.assertEqual(decoded.authorized_by, "cli")
        self.assertEqual(decoded.authorization_source, "manual")
        self.assertEqual(decoded.status, "authorized_submit")
        self.assertEqual(decoded.correlation_id, "application:55")

    def test_application_submitted_round_trip_json_preserves_payload_and_metadata(self) -> None:
        event = ApplicationSubmittedV1(
            application_id=55,
            job_id=123,
            portal="LinkedIn",
            confirmation_reference="ok-123",
            submitted_url="https://www.linkedin.com/jobs/view/123/",
            event_id="evt-submitted",
            occurred_at="2026-04-24T12:05:00+00:00",
            correlation_id="application:55",
        )

        decoded = event_from_json(event_to_json(event))

        self.assertIsInstance(decoded, ApplicationSubmittedV1)
        self.assertEqual(decoded.event_type, "ApplicationSubmittedV1")
        self.assertEqual(decoded.application_id, 55)
        self.assertEqual(decoded.job_id, 123)
        self.assertEqual(decoded.portal, "LinkedIn")
        self.assertEqual(decoded.confirmation_reference, "ok-123")
        self.assertEqual(decoded.submitted_url, "https://www.linkedin.com/jobs/view/123/")
        self.assertEqual(decoded.correlation_id, "application:55")

    def test_application_blocked_round_trip_json_preserves_payload_and_metadata(self) -> None:
        event = ApplicationBlockedV1(
            application_id=55,
            job_id=123,
            reason="outside_schedule",
            detail="janela operacional fechada",
            retryable=True,
            event_id="evt-blocked",
            occurred_at="2026-04-24T12:06:00+00:00",
            correlation_id="application:55",
        )

        decoded = event_from_json(event_to_json(event))

        self.assertIsInstance(decoded, ApplicationBlockedV1)
        self.assertEqual(decoded.event_type, "ApplicationBlockedV1")
        self.assertEqual(decoded.application_id, 55)
        self.assertEqual(decoded.job_id, 123)
        self.assertEqual(decoded.reason, "outside_schedule")
        self.assertEqual(decoded.detail, "janela operacional fechada")
        self.assertTrue(decoded.retryable)
        self.assertEqual(decoded.correlation_id, "application:55")

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
