from unittest import TestCase

from job_hunter_agent.core.legacy_matching_config import LegacyMatchingConfig
from job_hunter_agent.core.matching import build_matching_criteria_from_legacy_config


class MatchingFromLegacyConfigTests(TestCase):
    def test_build_matching_criteria_from_legacy_config_projects_contract_and_relaxation(self) -> None:
        criteria = build_matching_criteria_from_legacy_config(
            legacy_matching=LegacyMatchingConfig(
                profile_text="Backend engineer",
                include_keywords=("java", "kotlin"),
                exclude_keywords=("junior", "php"),
                accepted_work_modes=("remote",),
                minimum_salary_brl=12000,
                minimum_relevance=7,
            ),
            relaxed_matching_for_testing=True,
            relaxed_testing_profile_hint="Considere tambem contexto pleno.",
            relaxed_testing_remove_exclude_keywords=("junior",),
            relaxed_testing_minimum_relevance=5,
        )

        self.assertIn("pleno", criteria.profile_text)
        self.assertEqual(criteria.include_keywords, ("java", "kotlin"))
        self.assertEqual(criteria.exclude_keywords, ("php",))
        self.assertEqual(criteria.accepted_work_modes, ("remote",))
        self.assertEqual(criteria.minimum_salary_brl, 12000)
        self.assertEqual(criteria.minimum_relevance, 5)
