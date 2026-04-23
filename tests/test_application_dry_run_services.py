from __future__ import annotations

import unittest

from job_hunter_agent.application.application_preflight import ApplicationPreflightService
from job_hunter_agent.application.application_submission import ApplicationSubmissionService
from job_hunter_agent.core.domain import JobApplication, JobPosting


def _sample_job(*, job_id: int) -> JobPosting:
    return JobPosting(
        id=job_id,
        title="Backend Java",
        company="ACME",
        location="Brasil",
        work_mode="remoto",
        salary_text="Nao informado",
        url=f"https://www.linkedin.com/jobs/view/{job_id}/",
        source_site="LinkedIn",
        summary="Resumo",
        relevance=8,
        rationale="Boa aderencia",
        external_key=f"key-{job_id}",
        status="approved",
    )


class ApplicationDryRunServiceTests(unittest.TestCase):
    def test_preflight_dry_run_returns_ready_without_persisting_state(self) -> None:
        application = JobApplication(id=7, job_id=10, status="confirmed", support_level="auto_supported")
        job = _sample_job(job_id=10)

        class _Repository:
            def get_application(self, application_id: int):
                return application

            def get_job(self, job_id: int):
                return job

            def mark_application_status(self, *args, **kwargs):
                raise AssertionError("dry-run should not persist state")

            def record_application_event(self, *args, **kwargs):
                raise AssertionError("dry-run should not record events")

        class _ReadinessChecker:
            def check_preflight_ready(self, current_job):
                return type("Readiness", (), {"ok": True, "failures": ()})()

        service = ApplicationPreflightService(
            _Repository(),
            flow_inspector=None,
            readiness_checker=_ReadinessChecker(),
        )

        result = service.run_dry_run_for_application(7)

        self.assertEqual(result.outcome, "ready")
        self.assertEqual(result.application_status, "confirmed")
        self.assertIn("dry-run preflight", result.detail)

    def test_submit_dry_run_returns_ready_without_persisting_state(self) -> None:
        application = JobApplication(
            id=8,
            job_id=11,
            status="authorized_submit",
            last_preflight_detail="preflight real | pronto_para_envio=sim",
        )
        job = _sample_job(job_id=11)

        class _Repository:
            def get_application(self, application_id: int):
                return application

            def get_job(self, job_id: int):
                return job

            def mark_application_status(self, *args, **kwargs):
                raise AssertionError("dry-run should not persist state")

            def record_application_event(self, *args, **kwargs):
                raise AssertionError("dry-run should not record events")

        class _ReadinessChecker:
            def check_submit_ready(self, current_job):
                return type("Readiness", (), {"ok": True, "failures": ()})()

        class _Applicant:
            def submit(self, application, job):
                raise AssertionError("dry-run should not call applicant")

        service = ApplicationSubmissionService(
            _Repository(),
            applicant=_Applicant(),
            readiness_checker=_ReadinessChecker(),
        )

        result = service.run_dry_run_for_application(8)

        self.assertEqual(result.outcome, "ready")
        self.assertEqual(result.application_status, "authorized_submit")
        self.assertIn("dry-run submit", result.detail)
