from unittest import TestCase

from job_hunter_agent.core.domain import JobPosting
from job_hunter_agent.llm.application_priority import DeterministicApplicationPriorityAssessor


def _sample_job(*, relevance: int, work_mode: str) -> JobPosting:
    return JobPosting(
        title="Backend Engineer",
        company="ACME",
        location="Brasil",
        work_mode=work_mode,
        salary_text="Nao informado",
        url="https://example.com/job-1",
        source_site="LinkedIn",
        summary="Vaga backend",
        relevance=relevance,
        rationale="teste",
        external_key="key-1",
    )


class ApplicationPriorityTests(TestCase):
    def test_deterministic_priority_assessor_respects_configured_thresholds(self) -> None:
        assessor = DeterministicApplicationPriorityAssessor(
            high_min_relevance=9,
            medium_min_relevance=7,
            preferred_work_modes=("remote",),
        )

        high = assessor.assess(_sample_job(relevance=9, work_mode="remote"))
        medium = assessor.assess(_sample_job(relevance=8, work_mode="presencial"))
        low = assessor.assess(_sample_job(relevance=6, work_mode="presencial"))

        self.assertEqual(high.level, "alta")
        self.assertEqual(medium.level, "media")
        self.assertEqual(low.level, "baixa")
