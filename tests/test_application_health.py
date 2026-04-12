from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from job_hunter_agent.application.application_health import (
    build_application_health_report,
    render_application_health_report,
)


class ApplicationHealthTests(unittest.TestCase):
    def test_build_application_health_report_flags_failures_and_warnings(self) -> None:
        settings = type(
            "Settings",
            (),
            {
                "database_path": Path("./jobs.db"),
                "linkedin_storage_state_path": Path("./linkedin-state.json"),
                "resume_path": Path("./resume.pdf"),
                "application_contact_email": "vinicius@example.com",
                "application_phone": "11999999999",
                "application_phone_country_code": "+55",
                "telegram_token": "SEU_TOKEN_AQUI",
                "telegram_chat_id": "SEU_CHAT_ID_AQUI",
                "ollama_model": "qwen2.5:7b",
                "ollama_url": "http://localhost:11434",
            },
        )()

        with patch(
            "job_hunter_agent.application.application_health.resolve_local_chromium",
            side_effect=RuntimeError("chromium ausente"),
        ), patch(
            "pathlib.Path.exists",
            side_effect=lambda self: str(self).endswith("jobs.db") or str(self).endswith("linkedin-state.json") or str(self).endswith("resume.pdf") or self == Path(".").resolve(),
        ), patch(
            "pathlib.Path.is_dir",
            side_effect=lambda self: False if str(self).endswith(("jobs.db", "linkedin-state.json", "resume.pdf")) else True,
        ), patch(
            "pathlib.Path.is_file",
            side_effect=lambda self: str(self).endswith(("linkedin-state.json", "resume.pdf")),
        ):
            report = build_application_health_report(settings)

        self.assertFalse(report.ok)
        rendered = render_application_health_report(report)
        self.assertIn("Health operacional: fail", rendered)
        self.assertIn("playwright_chromium=fail", rendered)
        self.assertIn("telegram=warn", rendered)
        self.assertIn("ollama=ok", rendered)

    def test_build_application_health_report_is_ok_when_required_items_are_present(self) -> None:
        temp_root = Path.cwd() / ".tmp-tests" / "health-checks"
        temp_root.mkdir(parents=True, exist_ok=True)
        database_path = temp_root / "jobs.db"
        linkedin_state = temp_root / "linkedin-state.json"
        resume_path = temp_root / "resume.pdf"
        linkedin_state.write_text("{}", encoding="utf-8")
        resume_path.write_text("pdf", encoding="utf-8")
        try:
            settings = type(
                "Settings",
                (),
                {
                    "database_path": database_path,
                    "linkedin_storage_state_path": linkedin_state,
                    "resume_path": resume_path,
                    "application_contact_email": "vinicius@example.com",
                    "application_phone": "11999999999",
                    "application_phone_country_code": "+55",
                    "telegram_token": "token-real",
                    "telegram_chat_id": "chat-real",
                    "ollama_model": "qwen2.5:7b",
                    "ollama_url": "http://localhost:11434",
                },
            )()

            with patch(
                "job_hunter_agent.application.application_health.resolve_local_chromium",
                return_value=Path("/tmp/chromium/chrome.exe"),
            ):
                report = build_application_health_report(settings)

            self.assertTrue(report.ok)
            rendered = render_application_health_report(report)
            self.assertIn("Health operacional: ok", rendered)
            self.assertIn("telegram=ok", rendered)
            self.assertIn("linkedin_session=ok", rendered)
        finally:
            for file_path in (linkedin_state, resume_path):
                if file_path.exists():
                    file_path.unlink()
            if temp_root.exists():
                temp_root.rmdir()
