from unittest import TestCase

from job_hunter_agent.core.legacy_matching_config import LegacyMatchingConfig
from job_hunter_agent.core.settings import Settings


class LegacyMatchingConfigTests(TestCase):
    def test_settings_build_legacy_matching_config_projects_only_legacy_fields(self) -> None:
        settings = Settings(
            telegram_token="token",
            telegram_chat_id="chat",
            profile_text="Backend engineer",
            include_keywords=("java", "kotlin"),
            exclude_keywords=("junior", "php"),
            accepted_work_modes=("remoto", "hibrido"),
            minimum_salary_brl=12000,
            minimum_relevance=7,
        )

        config = settings.build_legacy_matching_config()

        self.assertEqual(
            config,
            LegacyMatchingConfig(
                profile_text="Backend engineer",
                include_keywords=("java", "kotlin"),
                exclude_keywords=("junior", "php"),
                accepted_work_modes=("remoto", "hibrido"),
                minimum_salary_brl=12000,
                minimum_relevance=7,
            ),
        )
