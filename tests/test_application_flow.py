from __future__ import annotations

import re
import unittest

from job_hunter_agent.application.application_flow import (
    ApplicationExecutionContext,
    ApplicationFlowCoordinator,
    load_application_context,
)
from job_hunter_agent.core.domain import JobApplication, JobPosting


def _sample_job(*, job_id: int) -> JobPosting:
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
        rationale="Boa aderencia",
        external_key=f"key-{job_id}",
        status="approved",
    )


class ApplicationFlowTests(unittest.TestCase):
    def test_load_application_context_returns_application_and_job(self) -> None:
        application = JobApplication(id=7, job_id=10, status="confirmed")
        job = _sample_job(job_id=10)

        class _Repository:
            def get_application(self, application_id: int):
                return application if application_id == 7 else None

            def get_job(self, job_id: int):
                return job if job_id == 10 else None

        context = load_application_context(_Repository(), 7)

        self.assertEqual(context, ApplicationExecutionContext(application=application, job=job))

    def test_load_application_context_raises_when_application_is_missing(self) -> None:
        class _Repository:
            def get_application(self, application_id: int):
                return None

            def get_job(self, job_id: int):
                return None

        with self.assertRaisesRegex(ValueError, "Application not found: 7"):
            load_application_context(_Repository(), 7)

    def test_load_application_context_raises_when_job_is_missing(self) -> None:
        application = JobApplication(id=7, job_id=10, status="confirmed")

        class _Repository:
            def get_application(self, application_id: int):
                return application

            def get_job(self, job_id: int):
                return None

        with self.assertRaisesRegex(ValueError, "Job not found for application: 7"):
            load_application_context(_Repository(), 7)

    def test_record_preflight_result_updates_status_and_records_transition_event(self) -> None:
        application = JobApplication(id=7, job_id=10, status="confirmed")
        context = ApplicationExecutionContext(application=application, job=_sample_job(job_id=10))

        class _Repository:
            def __init__(self) -> None:
                self.mark_calls = []
                self.event_calls = []

            def mark_application_status(self, application_id: int, **kwargs):
                self.mark_calls.append((application_id, kwargs))

            def record_application_event(self, application_id: int, **kwargs):
                self.event_calls.append((application_id, kwargs))

        repository = _Repository()
        flow = ApplicationFlowCoordinator(repository)

        status = flow.record_preflight_result(
            context,
            outcome="ready",
            detail="preflight real ok",
            event_type="preflight_ready",
            status="confirmed",
            clear_error=True,
        )

        self.assertEqual(status, "confirmed")
        self.assertEqual(
            repository.mark_calls,
            [
                (
                    7,
                    {
                        "status": "confirmed",
                        "event_detail": "preflight real ok",
                        "last_preflight_detail": "preflight real ok",
                        "last_error": "",
                    },
                )
            ],
        )
        self.assertEqual(
            repository.event_calls,
            [
                (
                    7,
                    {
                        "event_type": "preflight_ready",
                        "detail": "preflight real ok",
                        "from_status": "confirmed",
                        "to_status": "confirmed",
                    },
                )
            ],
        )

    def test_record_submit_result_updates_status_and_records_transition_event(self) -> None:
        application = JobApplication(id=8, job_id=11, status="authorized_submit")
        context = ApplicationExecutionContext(application=application, job=_sample_job(job_id=11))

        class _Repository:
            def __init__(self) -> None:
                self.mark_calls = []
                self.event_calls = []

            def mark_application_status(self, application_id: int, **kwargs):
                self.mark_calls.append((application_id, kwargs))

            def record_application_event(self, application_id: int, **kwargs):
                self.event_calls.append((application_id, kwargs))

        repository = _Repository()
        flow = ApplicationFlowCoordinator(repository)

        status = flow.record_submit_result(
            context,
            detail="submissao real concluida no LinkedIn",
            event_type="submit_submitted",
            status="submitted",
            clear_error=True,
            submitted_at="2026-04-12T00:10:00",
        )

        self.assertEqual(status, "submitted")
        self.assertEqual(
            repository.mark_calls,
            [
                (
                    8,
                    {
                        "status": "submitted",
                        "event_detail": "submissao real concluida no LinkedIn",
                        "last_submit_detail": "submissao real concluida no LinkedIn",
                        "last_error": "",
                        "submitted_at": "2026-04-12T00:10:00",
                    },
                )
            ],
        )
        self.assertEqual(
            repository.event_calls,
            [
                (
                    8,
                    {
                        "event_type": "submit_submitted",
                        "detail": "submissao real concluida no LinkedIn",
                        "from_status": "authorized_submit",
                        "to_status": "submitted",
                    },
                )
            ],
        )

    def test_resolve_submitted_at_uses_current_timestamp_when_missing(self) -> None:
        resolved = ApplicationFlowCoordinator.resolve_submitted_at(None)

        self.assertRegex(resolved, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")

    def test_resolve_submitted_at_preserves_explicit_value(self) -> None:
        resolved = ApplicationFlowCoordinator.resolve_submitted_at("2026-04-12T00:15:00")

        self.assertEqual(resolved, "2026-04-12T00:15:00")
