from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from job_hunter_agent.collectors.linkedin_application_inspection import inspect_linkedin_application
from job_hunter_agent.collectors.linkedin_application_state import (
    LinkedInApplicationInspection,
    LinkedInApplicationPageState,
)


class LinkedInApplicationInspectionFlowTests(unittest.TestCase):
    def test_inspect_linkedin_application_returns_blocked_when_readiness_is_not_ready(self) -> None:
        job = type("Job", (), {"url": "https://www.linkedin.com/jobs/view/123/"})()

        async def fake_ensure(page, current_job):
            return None

        async def fake_read(page, current_job):
            return (
                LinkedInApplicationPageState(easy_apply=False),
                type("Readiness", (), {"result": "listing_redirect", "reason": "redirect", "sample": "sample"})(),
            )

        async def fake_capture(page, **kwargs):
            return " | artefatos=ok"

        async def fake_preflight(page, state):
            return state

        async def fake_run_with_linkedin_page(*, storage_state_path, headless, page_operation):
            class _Page:
                async def goto(self, url, wait_until="domcontentloaded"):
                    return None

            return await page_operation(_Page())

        with patch(
            "job_hunter_agent.collectors.linkedin_application_inspection.run_with_linkedin_page",
            side_effect=fake_run_with_linkedin_page,
        ):
            result = inspect_linkedin_application(
                job=job,
                storage_state_path=Path("linkedin-state.json"),
                headless=True,
                ensure_target_job_page=fake_ensure,
                read_state_with_hydration=fake_read,
                capture_failure_artifacts=fake_capture,
                inspect_preflight_state=fake_preflight,
                classify_page_state=lambda state: LinkedInApplicationInspection(outcome="ready", detail="ok"),
                modal_interpretation_formatter=None,
            )
            inspection = __import__("asyncio").run(result)

        self.assertEqual(inspection.outcome, "blocked")
        self.assertIn("bloqueio_funcional:", inspection.detail)
        self.assertIn("preflight real bloqueado", inspection.detail)
        self.assertIn("artefatos=ok", inspection.detail)

    def test_inspect_linkedin_application_appends_modal_interpretation(self) -> None:
        job = type("Job", (), {"url": "https://www.linkedin.com/jobs/view/123/"})()

        async def fake_ensure(page, current_job):
            return None

        async def fake_read(page, current_job):
            return (
                LinkedInApplicationPageState(easy_apply=True, modal_open=True),
                type("Readiness", (), {"result": "ready", "reason": "", "sample": ""})(),
            )

        async def fake_capture(page, **kwargs):
            return ""

        async def fake_preflight(page, state):
            return state

        async def fake_run_with_linkedin_page(*, storage_state_path, headless, page_operation):
            class _Page:
                async def goto(self, url, wait_until="domcontentloaded"):
                    return None

            return await page_operation(_Page())

        with patch(
            "job_hunter_agent.collectors.linkedin_application_inspection.run_with_linkedin_page",
            side_effect=fake_run_with_linkedin_page,
        ):
            result = inspect_linkedin_application(
                job=job,
                storage_state_path=Path("linkedin-state.json"),
                headless=True,
                ensure_target_job_page=fake_ensure,
                read_state_with_hydration=fake_read,
                capture_failure_artifacts=fake_capture,
                inspect_preflight_state=fake_preflight,
                classify_page_state=lambda state: LinkedInApplicationInspection(outcome="ready", detail="base"),
                modal_interpretation_formatter=lambda state: "acao=submit_if_authorized",
            )
            inspection = __import__("asyncio").run(result)

        self.assertEqual(inspection.outcome, "ready")
        self.assertIn("base | acao=submit_if_authorized", inspection.detail)
