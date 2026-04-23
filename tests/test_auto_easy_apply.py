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
        last_preflight_detail="preflight real ok | pronto_para_envio=sim",
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
            "auto_easy_apply_max_blocks_same_reason": 5,
            "auto_easy_apply_allowed_start_hour": 0,
            "auto_easy_apply_allowed_end_hour": 0,
            "auto_easy_apply_denylist_company_terms": (),
            "auto_easy_apply_denylist_url_terms": (),
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

    def test_run_once_skips_company_in_denylist(self) -> None:
        repository = _FakeRepository(
            applications=[_application(app_id=1, job_id=10)],
            jobs={10: _job(job_id=10)},
        )
        service = AutoEasyApplyService(
            repository=repository,
            preflight=_FakePreflight(),
            submission=_FakeSubmission(),
            transitions=_FakeTransitions(),
            settings=self._settings(auto_easy_apply_denylist_company_terms=("acme",)),
        )

        report = service.run_once()

        self.assertEqual(report.submitted, 0)
        self.assertEqual(report.skipped, 1)
        self.assertIn("empresa_na_denylist", " | ".join(report.details))

    def test_run_once_blocks_outside_allowed_window(self) -> None:
        repository = _FakeRepository(
            applications=[_application(app_id=1, job_id=10)],
            jobs={10: _job(job_id=10)},
        )
        service = AutoEasyApplyService(
            repository=repository,
            preflight=_FakePreflight(),
            submission=_FakeSubmission(),
            transitions=_FakeTransitions(),
            settings=self._settings(
                auto_easy_apply_allowed_start_hour=10,
                auto_easy_apply_allowed_end_hour=11,
            ),
        )

        fake_now = type("FakeNow", (), {"hour": 12})()
        with patch("job_hunter_agent.application.auto_easy_apply.datetime") as dt_mock:
            dt_mock.now.return_value = fake_now
            report = service.run_once()

        self.assertEqual(report.submitted, 0)
        self.assertEqual(report.blocked, 1)
        self.assertIn("fora da janela horaria", " | ".join(report.details))

    def test_run_once_stops_when_same_block_reason_reaches_limit(self) -> None:
        class _ErrorSubmission:
            def __init__(self) -> None:
                self.called: list[int] = []

            def run_for_application(self, application_id: int):
                self.called.append(application_id)
                return type("Result", (), {"outcome": "error", "detail": "falha"})()

        repository = _FakeRepository(
            applications=[
                _application(app_id=1, job_id=10),
                _application(app_id=2, job_id=11),
                _application(app_id=3, job_id=12),
            ],
            jobs={
                10: _job(job_id=10),
                11: _job(job_id=11),
                12: _job(job_id=12),
            },
        )
        submission = _ErrorSubmission()
        service = AutoEasyApplyService(
            repository=repository,
            preflight=_FakePreflight(),
            submission=submission,
            transitions=_FakeTransitions(),
            settings=self._settings(
                auto_easy_apply_cooldown_seconds=0,
                auto_easy_apply_max_consecutive_errors=5,
                auto_easy_apply_max_blocks_same_reason=2,
            ),
        )

        report = service.run_once()

        self.assertEqual(report.submitted, 0)
        self.assertEqual(report.blocked, 2)
        self.assertEqual(submission.called, [1, 2])
        self.assertIn("parada por bloqueio repetido", " | ".join(report.details))
