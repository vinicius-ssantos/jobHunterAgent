from unittest import TestCase

from job_hunter_agent.settings import Settings, load_settings


class SettingsTests(TestCase):
    def test_validate_rejects_placeholder_token(self) -> None:
        with self.assertRaises(ValueError):
            Settings(telegram_token="SEU_TOKEN_AQUI", telegram_chat_id="chat")

    def test_load_settings_reads_environment_overrides(self) -> None:
        settings = Settings(
            telegram_token="token",
            telegram_chat_id="chat",
            profile_text="Backend engineer",
            collection_time="09:30",
        )

        self.assertEqual(settings.telegram_token, "token")
        self.assertEqual(settings.telegram_chat_id, "chat")
        self.assertEqual(settings.profile_text, "Backend engineer")
        self.assertEqual(settings.collection_time, "09:30")
        self.assertEqual(settings.review_polling_grace_seconds, 120)
        self.assertEqual(settings.linkedin_max_pages_per_cycle, 2)
        self.assertEqual(settings.linkedin_max_page_depth, 6)
        self.assertFalse(settings.relaxed_matching_for_testing)
        self.assertTrue(settings.linkedin_field_repair_enabled)
        self.assertTrue(settings.application_priority_llm_enabled)

    def test_load_settings_from_env_prefix(self) -> None:
        previous_prefix = Settings.model_config.get("env_prefix")
        previous_env_file = Settings.model_config.get("env_file")
        Settings.model_config["env_prefix"] = "JOB_HUNTER_"
        Settings.model_config["env_file"] = None
        try:
            import os
            from unittest.mock import patch

            with patch.dict(
                os.environ,
                {
                    "JOB_HUNTER_TELEGRAM_TOKEN": "token",
                    "JOB_HUNTER_TELEGRAM_CHAT_ID": "chat",
                    "JOB_HUNTER_PROFILE_TEXT": "Backend engineer",
                    "JOB_HUNTER_COLLECTION_TIME": "09:30",
                },
                clear=False,
            ):
                settings = load_settings()
        finally:
            Settings.model_config["env_prefix"] = previous_prefix
            Settings.model_config["env_file"] = previous_env_file

        self.assertEqual(settings.telegram_token, "token")
        self.assertEqual(settings.telegram_chat_id, "chat")

    def test_rejects_invalid_collection_time(self) -> None:
        with self.assertRaises(ValueError):
            Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                collection_time="99:99",
            )

    def test_rejects_without_chat_id(self) -> None:
        with self.assertRaises(ValueError):
            Settings(
                telegram_token="token",
                telegram_chat_id="",
            )

    def test_rejects_without_active_sites(self) -> None:
        from job_hunter_agent.domain import SiteConfig

        with self.assertRaises(ValueError):
            Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                sites=(SiteConfig(name="LinkedIn", search_url="https://example.com", enabled=False),),
            )

    def test_relaxed_matching_for_testing_changes_scoring_inputs(self) -> None:
        settings = Settings(
            telegram_token="token",
            telegram_chat_id="chat",
            relaxed_matching_for_testing=True,
        )

        self.assertNotIn("junior", settings.scoring_exclude_keywords)
        self.assertIn("junior e pleno", settings.scoring_profile_text)
        self.assertEqual(settings.scoring_minimum_relevance, 4)

    def test_relaxed_matching_for_testing_can_be_tuned_by_settings(self) -> None:
        settings = Settings(
            telegram_token="token",
            telegram_chat_id="chat",
            relaxed_matching_for_testing=True,
            relaxed_testing_profile_hint="Aceite tambem vagas pleno e mid-level.",
            relaxed_testing_remove_exclude_keywords=("junior", "trainee"),
            relaxed_testing_minimum_relevance=5,
        )

        self.assertIn("pleno e mid-level", settings.scoring_profile_text)
        self.assertNotIn("junior", settings.scoring_exclude_keywords)
        self.assertNotIn("trainee", settings.scoring_exclude_keywords)
        self.assertEqual(settings.scoring_minimum_relevance, 5)

    def test_rejects_invalid_linkedin_max_pages_per_cycle(self) -> None:
        with self.assertRaises(ValueError):
            Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                linkedin_max_pages_per_cycle=0,
            )

    def test_rejects_invalid_linkedin_max_page_depth(self) -> None:
        with self.assertRaises(ValueError):
            Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                linkedin_max_page_depth=0,
            )
