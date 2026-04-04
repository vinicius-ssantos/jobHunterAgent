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
