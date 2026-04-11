from types import SimpleNamespace
from unittest import TestCase

from job_hunter_agent.infrastructure.notifier import TelegramNotifier


class TelegramNotifierSettingsTests(TestCase):
    def test_requires_real_token_when_telegram_is_enabled(self) -> None:
        settings = SimpleNamespace(
            telegram_token="SEU_TOKEN_AQUI",
            telegram_chat_id="chat",
        )

        with self.assertRaisesRegex(ValueError, "JOB_HUNTER_TELEGRAM_TOKEN"):
            TelegramNotifier(settings=settings, repository=object())

    def test_requires_real_chat_id_when_telegram_is_enabled(self) -> None:
        settings = SimpleNamespace(
            telegram_token="token",
            telegram_chat_id="SEU_CHAT_ID_AQUI",
        )

        with self.assertRaisesRegex(ValueError, "JOB_HUNTER_TELEGRAM_CHAT_ID"):
            TelegramNotifier(settings=settings, repository=object())
