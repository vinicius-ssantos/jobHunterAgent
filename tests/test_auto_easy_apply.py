from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from job_hunter_agent.application.auto_easy_apply import AutoEasyApplyService
from job_hunter_agent.core.domain import JobApplication, JobPosting


def _job(*, job_id: int, relevance: int = 9, status: str = "approved") -> JobPosting:
    return JobPosting(
        id=job_id,
        title="Backend Java",
        company="ACME",
        location="Brasil",
        work_mode="remoto",
        salary_text="Nao informado",
        url=f"https://www.linkedin.com/jobs/view/{job_id}/",
        source_site="LinkedIn",
        summary="Java backend",
        relevance=relevance,
        rationale="fit",
        external_key=f"key-{job_id}",
        status=status,
    )


def _application(*, app_id: int, job_id: int, status: str = "authorized_submit") -> JobApplication:
    return JobApplication(
        id=app_id,
        job_id=job_id,
        status=status,
        support_level="manual_review",
    )


class _FakeRepository:
    def __init__(self, applications: list[JobApplication], jobs: dict[int, JobPosting], submitted_today: int = 0) -> None:
        self._applications = applications
        self._jobs = jobs
        self.submitted_today = submitted_today

    def count_submitted_applications_since(self, since: str) -> int:
        return self.submitted_today

    def list_applications_by_status(self, status: str) -> list[JobApplication]:
        return [item for item in self._applications if item.status == status]

    def get_job(self, job_id: int):
        return self._jobs.get(job_id)

    def get_application(self, application_id: int):
        for item in self._applications:
            if item.id == application_id:
                return item
        return None


class _FakePreflight:
    def run_for_application(self, application_id: int):
        return type("Result", (), {"outcome": "ready", "detail": "ok"})()


class _FakeTransitions:
    def authorize_application(self, application_id: int) -> str:
        return f"autorizada {application_id}"


class _FakeSubmission:
    def __init__(self) -> None:
        self.called: list[int] = []

    def run_for_application(self, application_id: int):
        self.called.append(application_id)
        return type("Result", (), {"outcome": "submitted", "detail": "ok"})()


class AutoEasyApplyServiceTests(TestCase):
    def _settings(self, **overrides):
        base = {
            "auto_easy_apply_enabled": True,
            "auto_easy_apply_min_score": 8,
            "auto_easy_apply_max_submits_per_cycle": 3,
            "auto_easy_apply_max_submits_per_day": 10,
            "auto_easy_apply_cooldown_seconds": 1,
            "auto_easy_apply_max_consecutive_errors": 2,
        }
        base.update(overrides)
        return type("Settings", (), base)()

    def test_run_once_submits_authorized_jobs_within_limits(self) -> None:
        repository = _FakeRepository(
            applications=[_application(app_id=1, job_id=10)],
            jobs={10: _job(job_id=10, relevance=9)},
        )
        submission = _FakeSubmission()
        service = AutoEasyApplyService(
            repository=repository,
            preflight=_FakePreflight(),
            submission=submission,
            transitions=_FakeTransitions(),
            settings=self._settings(auto_easy_apply_cooldown_seconds=0),
        )

        report = service.run_once()

        self.assertEqual(report.submitted, 1)
        self.assertEqual(report.blocked, 0)
        self.assertEqual(report.skipped, 0)
        self.assertEqual(submission.called, [1])

    def test_run_once_skips_below_min_score(self) -> None:
        repository = _FakeRepository(
            applications=[_application(app_id=1, job_id=10)],
            jobs={10: _job(job_id=10, relevance=6)},
        )
        service = AutoEasyApplyService(
            repository=repository,
            preflight=_FakePreflight(),
            submission=_FakeSubmission(),
            transitions=_FakeTransitions(),
            settings=self._settings(),
        )

        report = service.run_once()

        self.assertEqual(report.submitted, 0)
        self.assertEqual(report.skipped, 1)
        self.assertIn("score_abaixo_do_limiar", " | ".join(report.details))

    def test_run_once_respects_daily_limit(self) -> None:
        repository = _FakeRepository(
            applications=[_application(app_id=1, job_id=10)],
            jobs={10: _job(job_id=10)},
            submitted_today=10,
        )
        service = AutoEasyApplyService(
            repository=repository,
            preflight=_FakePreflight(),
            submission=_FakeSubmission(),
            transitions=_FakeTransitions(),
            settings=self._settings(auto_easy_apply_max_submits_per_day=10),
        )

        report = service.run_once()

        self.assertEqual(report.submitted, 0)
        self.assertEqual(report.blocked, 1)
        self.assertIn("limite diario atingido", " | ".join(report.details))

    def test_run_once_applies_cooldown_between_successful_submissions(self) -> None:
        repository = _FakeRepository(
            applications=[
                _application(app_id=1, job_id=10),
                _application(app_id=2, job_id=11),
            ],
            jobs={
                10: _job(job_id=10, relevance=9),
                11: _job(job_id=11, relevance=9),
            },
        )
        submission = _FakeSubmission()
        service = AutoEasyApplyService(
            repository=repository,
            preflight=_FakePreflight(),
            submission=submission,
            transitions=_FakeTransitions(),
            settings=self._settings(auto_easy_apply_max_submits_per_cycle=2, auto_easy_apply_cooldown_seconds=3),
        )

        with patch("time.sleep") as sleep_mock:
            report = service.run_once()

        self.assertEqual(report.submitted, 2)
        sleep_mock.assert_called_once_with(3)
