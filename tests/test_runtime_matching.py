from unittest import TestCase

from job_hunter_agent.core.matching_reasons import (
    REASON_EXCLUDED_KEYWORDS,
    REASON_SALARY_BELOW_MINIMUM,
    REASON_SENIORITY_OUTSIDE_TARGET,
    REASON_UNKNOWN_SENIORITY,
    REASON_WORK_MODE_MISMATCH,
)
from job_hunter_agent.core.runtime_matching import (
    RuntimeMatchingPolicy,
    RuntimeMatchingProfile,
    runtime_rejection_reason_to_rationale,
)


class RuntimeMatchingTests(TestCase):
    def test_prefilter_reason_prioritizes_seniority_before_work_mode_and_salary(self) -> None:
        policy = RuntimeMatchingPolicy(
            RuntimeMatchingProfile(
                candidate_summary="Backend engineer",
                include_keywords=("java",),
                exclude_keywords=(),
                accepted_work_modes=("remote",),
                minimum_salary_brl=10000,
                minimum_relevance=6,
                target_seniorities=("senior",),
                allow_unknown_seniority=True,
            )
        )

        reason = policy.evaluate_prefilter_reason(
            text="junior backend engineer java",
            work_mode="onsite",
            salary_floor=5000,
        )

        self.assertEqual(reason, REASON_SENIORITY_OUTSIDE_TARGET)

    def test_prefilter_reason_rejects_excluded_keywords_before_other_dimensions(self) -> None:
        policy = RuntimeMatchingPolicy(
            RuntimeMatchingProfile(
                candidate_summary="Backend engineer",
                include_keywords=("java",),
                exclude_keywords=("php",),
                accepted_work_modes=("remote",),
                minimum_salary_brl=10000,
                minimum_relevance=6,
                target_seniorities=("senior",),
                allow_unknown_seniority=False,
            )
        )

        reason = policy.evaluate_prefilter_reason(
            text="junior php developer presencial",
            work_mode="onsite",
            salary_floor=5000,
        )

        self.assertEqual(reason, REASON_EXCLUDED_KEYWORDS)

    def test_prefilter_reason_rejects_unknown_seniority_when_not_allowed(self) -> None:
        policy = RuntimeMatchingPolicy(
            RuntimeMatchingProfile(
                candidate_summary="Backend engineer",
                include_keywords=("java",),
                exclude_keywords=(),
                accepted_work_modes=(),
                minimum_salary_brl=0,
                minimum_relevance=6,
                target_seniorities=("senior",),
                allow_unknown_seniority=False,
            )
        )

        reason = policy.evaluate_prefilter_reason(
            text="backend engineer java",
            work_mode="remote",
            salary_floor=None,
        )

        self.assertEqual(reason, REASON_UNKNOWN_SENIORITY)

    def test_prefilter_reason_accepts_unknown_seniority_when_allowed(self) -> None:
        policy = RuntimeMatchingPolicy(
            RuntimeMatchingProfile(
                candidate_summary="Backend engineer",
                include_keywords=("java",),
                exclude_keywords=(),
                accepted_work_modes=(),
                minimum_salary_brl=0,
                minimum_relevance=6,
                target_seniorities=("senior",),
                allow_unknown_seniority=True,
            )
        )

        reason = policy.evaluate_prefilter_reason(
            text="backend engineer java",
            work_mode="remote",
            salary_floor=None,
        )

        self.assertIsNone(reason)

    def test_prefilter_reason_rejects_work_mode_when_seniority_and_keywords_pass(self) -> None:
        policy = RuntimeMatchingPolicy(
            RuntimeMatchingProfile(
                candidate_summary="Backend engineer",
                include_keywords=("java",),
                exclude_keywords=(),
                accepted_work_modes=("remote",),
                minimum_salary_brl=0,
                minimum_relevance=6,
                target_seniorities=("senior",),
                allow_unknown_seniority=True,
            )
        )

        reason = policy.evaluate_prefilter_reason(
            text="senior backend engineer java",
            work_mode="presencial",
            salary_floor=None,
        )

        self.assertEqual(reason, REASON_WORK_MODE_MISMATCH)

    def test_prefilter_reason_rejects_salary_when_previous_dimensions_pass(self) -> None:
        policy = RuntimeMatchingPolicy(
            RuntimeMatchingProfile(
                candidate_summary="Backend engineer",
                include_keywords=("java",),
                exclude_keywords=(),
                accepted_work_modes=("remote",),
                minimum_salary_brl=10000,
                minimum_relevance=6,
                target_seniorities=("senior",),
                allow_unknown_seniority=True,
            )
        )

        reason = policy.evaluate_prefilter_reason(
            text="senior backend engineer java",
            work_mode="remote",
            salary_floor=5000,
        )

        self.assertEqual(reason, REASON_SALARY_BELOW_MINIMUM)

    def test_prefilter_reason_accepts_when_all_deterministic_dimensions_pass(self) -> None:
        policy = RuntimeMatchingPolicy(
            RuntimeMatchingProfile(
                candidate_summary="Backend engineer",
                include_keywords=("java",),
                exclude_keywords=("php",),
                accepted_work_modes=("remote",),
                minimum_salary_brl=10000,
                minimum_relevance=6,
                target_seniorities=("senior",),
                allow_unknown_seniority=True,
            )
        )

        reason = policy.evaluate_prefilter_reason(
            text="senior backend engineer java spring",
            work_mode="remote",
            salary_floor=15000,
        )

        self.assertIsNone(reason)

    def test_runtime_rejection_reason_to_rationale_maps_new_path_tokens(self) -> None:
        self.assertEqual(runtime_rejection_reason_to_rationale(REASON_EXCLUDED_KEYWORDS), "termos_excluidos")
        self.assertEqual(runtime_rejection_reason_to_rationale(REASON_SENIORITY_OUTSIDE_TARGET), "senioridade_fora_do_alvo")
        self.assertEqual(runtime_rejection_reason_to_rationale(REASON_UNKNOWN_SENIORITY), "senioridade_nao_informada")
        self.assertEqual(runtime_rejection_reason_to_rationale(REASON_WORK_MODE_MISMATCH), "modalidade_incompativel")
        self.assertEqual(runtime_rejection_reason_to_rationale(REASON_SALARY_BELOW_MINIMUM), "salario_abaixo")
