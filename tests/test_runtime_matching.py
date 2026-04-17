from unittest import TestCase

from job_hunter_agent.core.matching_reasons import (
    REASON_SALARY_BELOW_MINIMUM,
    REASON_SENIORITY_OUTSIDE_TARGET,
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

    def test_runtime_rejection_reason_to_rationale_maps_new_path_tokens(self) -> None:
        self.assertEqual(runtime_rejection_reason_to_rationale(REASON_SENIORITY_OUTSIDE_TARGET), "senioridade_fora_do_alvo")
        self.assertEqual(runtime_rejection_reason_to_rationale(REASON_WORK_MODE_MISMATCH), "modalidade_incompativel")
        self.assertEqual(runtime_rejection_reason_to_rationale(REASON_SALARY_BELOW_MINIMUM), "salario_abaixo")
