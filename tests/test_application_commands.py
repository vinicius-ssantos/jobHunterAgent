import unittest

from job_hunter_agent.application.application_commands import (
    ApplicationDraftCommandService,
    ApplicationTransitionCommandService,
    JobReviewCommandService,
)
from job_hunter_agent.core.domain import JobApplication, JobPosting


def _sample_job(*, job_id: int, status: str) -> JobPosting:
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
        status=status,
    )


class JobReviewCommandServiceTests(unittest.TestCase):
    def test_review_job_marks_status_when_transition_is_valid(self) -> None:
        class _Repository:
            def __init__(self) -> None:
                self.marked: list[tuple[int, str, str]] = []

            def get_job(self, job_id: int):
                return _sample_job(job_id=job_id, status="collected")

            def mark_status(self, job_id: int, status: str, *, detail: str = ""):
                self.marked.append((job_id, status, detail))

        repository = _Repository()
        service = JobReviewCommandService(repository)

        detail = service.review_job(8, "approve")

        self.assertEqual(detail, "Vaga aprovada: Backend Java - ACME")
        self.assertEqual(repository.marked, [(8, "approved", "Vaga aprovada: Backend Java - ACME")])


class ApplicationDraftCommandServiceTests(unittest.TestCase):
    def test_create_application_draft_for_job_returns_existing_application(self) -> None:
        class _Repository:
            def get_job(self, job_id: int):
                return _sample_job(job_id=job_id, status="approved")

            def get_application_by_job(self, job_id: int):
                return JobApplication(id=21, job_id=job_id, status="confirmed", support_level="manual_review")

        class _PreparationService:
            def create_drafts_for_approved_jobs(self, job_ids: list[int], notes: str = ""):
                raise AssertionError("nao deveria criar novo draft")

        service = ApplicationDraftCommandService(_Repository(), _PreparationService())

        detail = service.create_application_draft_for_job(10)

        self.assertEqual(
            detail,
            "Candidatura ja existe para a vaga: application_id=21 status=confirmed job_id=10",
        )


class ApplicationTransitionCommandServiceTests(unittest.TestCase):
    def test_authorize_application_uses_transition_service(self) -> None:
        class _Repository:
            def __init__(self) -> None:
                self.marked: list[tuple[int, str, str]] = []

            def get_application(self, application_id: int):
                return JobApplication(id=application_id, job_id=5, status="confirmed")

            def mark_application_status(self, application_id: int, *, status: str, event_detail: str = "", **kwargs):
                self.marked.append((application_id, status, event_detail))

        repository = _Repository()
        service = ApplicationTransitionCommandService(repository)

        detail = service.authorize_application(9)

        self.assertEqual(detail, "Candidatura autorizada para envio: id=9")
        self.assertEqual(
            repository.marked,
            [(9, "authorized_submit", "Candidatura autorizada para envio: id=9")],
        )
