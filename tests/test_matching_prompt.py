from unittest import TestCase

from job_hunter_agent.core.domain import RawJob
from job_hunter_agent.core.matching_prompt import build_runtime_scoring_prompt, build_scoring_rationale_guidance
from job_hunter_agent.core.runtime_matching import RuntimeMatchingProfile


class MatchingPromptTests(TestCase):
    def test_build_runtime_scoring_prompt_includes_guidance_and_profile(self) -> None:
        raw_job = RawJob(
            title="Senior Backend Engineer",
            company="Acme",
            location="Brasil",
            work_mode="Remote",
            salary_text="R$ 20.000",
            url="https://example.com/job",
            source_site="LinkedIn",
            summary="Java e Kotlin",
            description="Atuacao com Spring Boot e AWS.",
        )
        profile = RuntimeMatchingProfile(
            candidate_summary="Engenheiro backend com foco em Java.",
            include_keywords=("java", "kotlin"),
            exclude_keywords=("junior", ".net"),
            accepted_work_modes=("remote", "hybrid"),
            minimum_salary_brl=10000,
            minimum_relevance=6,
        )

        prompt = build_runtime_scoring_prompt(raw_job, profile)

        self.assertIn("Perfil:", prompt)
        self.assertIn("Engenheiro backend com foco em Java.", prompt)
        self.assertIn("stack_alinhada", prompt)
        self.assertIn("modalidade_compativel", prompt)
        self.assertIn("Salario minimo em BRL: 10000", prompt)

    def test_build_scoring_rationale_guidance_mentions_short_consistent_tokens(self) -> None:
        guidance = build_scoring_rationale_guidance()

        self.assertIn("tokens curtos", guidance)
        self.assertIn("senioridade_compativel", guidance)
        self.assertIn("sinais_insuficientes", guidance)
        self.assertIn("modalidade_incompativel", guidance)
