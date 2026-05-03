from unittest import TestCase

from job_hunter_agent.core.matching_reasons import (
    REASON_SENIORITY_OUTSIDE_TARGET,
    REASON_UNKNOWN_SENIORITY,
)
from job_hunter_agent.core.runtime_matching import RuntimeMatchingPolicy, RuntimeMatchingProfile


class MatchingSeniorityPolicyTests(TestCase):
    def test_policy_rejects_job_outside_target_seniority(self) -> None:
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

        reason = policy.evaluate_seniority_reason("junior backend engineer java kotlin")

        self.assertEqual(reason, REASON_SENIORITY_OUTSIDE_TARGET)

    def test_policy_rejects_unknown_seniority_when_not_allowed(self) -> None:
        policy = RuntimeMatchingPolicy(
            RuntimeMatchingProfile(
                candidate_summary="Backend engineer",
                include_keywords=("java",),
                exclude_keywords=(),
                accepted_work_modes=("remote",),
                minimum_salary_brl=10000,
                minimum_relevance=6,
                target_seniorities=("senior",),
                allow_unknown_seniority=False,
            )
        )

        reason = policy.evaluate_seniority_reason("backend engineer java kotlin")

        self.assertEqual(reason, REASON_UNKNOWN_SENIORITY)

    def test_policy_accepts_unknown_seniority_when_allowed(self) -> None:
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

        reason = policy.evaluate_seniority_reason("backend engineer java kotlin")

        self.assertIsNone(reason)
