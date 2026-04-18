from unittest import TestCase

from job_hunter_agent.core.domain import RawJob
from job_hunter_agent.core.matching_prompt import build_legacy_scoring_prompt
from job_hunter_agent.core.runtime_matching import RuntimeMatchingProfile


class MatchingPromptStructuredSeniorityTests(TestCase):
    def test_prompt_mentions_target_seniorities_and_unknown_seniority_policy(self) -> None:
        prompt = build_legacy_scoring_prompt(
            RawJob(
                title="Senior Backend Engineer",
                company="Acme",
                location="Brasil",
                work_mode="Remote",
                salary_text="R$ 20.000",
                url="https://example.com/job",
                source_site="LinkedIn",
                summary="Java e Kotlin",
                description="Atuacao com Spring Boot e AWS.",
            ),
            RuntimeMatchingProfile(
                candidate_summary="Engenheiro backend com foco em Java.",
                include_keywords=("java", "kotlin"),
                exclude_keywords=("junior", ".net"),
                accepted_work_modes=("remote", "hybrid"),
                minimum_salary_brl=10000,
                minimum_relevance=6,
                target_seniorities=("senior", "especialista"),
                allow_unknown_seniority=False,
            ),
        )

        self.assertIn("Senioridades alvo: senior, especialista", prompt)
        self.assertIn("Aceitar senioridade nao informada: nao", prompt)
        self.assertIn("senioridade_fora_do_alvo", prompt)
        self.assertIn("senioridade_nao_informada", prompt)
