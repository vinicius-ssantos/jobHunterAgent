from __future__ import annotations

import asyncio
import unittest
from pathlib import Path
from unittest.mock import patch

from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState
from job_hunter_agent.collectors.linkedin_application_submission_flow import submit_linkedin_application


class LinkedInApplicationSubmissionFlowTests(unittest.TestCase):
    def test_submit_linkedin_application_returns_error_when_cta_is_missing(self) -> None:
        job = type("Job", (), {"url": "https://www.linkedin.com/jobs/view/123/"})()

        async def fake_ensure(page, current_job):
            return None

        async def fake_read(page, current_job):
            return (
                LinkedInApplicationPageState(easy_apply=False),
                type("Readiness", (), {"result": "ready", "reason": "", "sample": ""})(),
            )

        async def fake_capture(page, **kwargs):
            return ""

        async def fake_prepare(page, state):
            return state

        async def fake_submit(page):
            return True

        async def fake_exception_result(exc, **kwargs):
            raise AssertionError("exception path should not run")

        async def fake_run_with_linkedin_page(*, storage_state_path, headless, page_operation):
            class _Page:
                async def goto(self, url, wait_until="domcontentloaded"):
                    return None

            return await page_operation(_Page())

        with patch(
            "job_hunter_agent.collectors.linkedin_application_submission_flow.run_with_linkedin_page",
            side_effect=fake_run_with_linkedin_page,
        ):
            result = asyncio.run(
                submit_linkedin_application(
                    job=job,
                    storage_state_path=Path("linkedin-state.json"),
                    headless=True,
                    ensure_target_job_page=fake_ensure,
                    read_state_with_hydration=fake_read,
                    capture_failure_artifacts=fake_capture,
                    prepare_submit_state=fake_prepare,
                    execution_submit=fake_submit,
                    format_modal_interpretation_for_error=lambda state: "",
                    build_submit_exception_result=fake_exception_result,
                )
            )

        self.assertEqual(result.status, "error_submit")
        self.assertIn("CTA de candidatura simplificada nao encontrado", result.detail)

    def test_submit_linkedin_application_returns_submitted_when_flow_succeeds(self) -> None:
        job = type("Job", (), {"url": "https://www.linkedin.com/jobs/view/123/"})()

        async def fake_ensure(page, current_job):
            return None

        async def fake_read(page, current_job):
            return (
                LinkedInApplicationPageState(easy_apply=True),
                type("Readiness", (), {"result": "ready", "reason": "", "sample": ""})(),
            )

        async def fake_capture(page, **kwargs):
            return ""

        async def fake_prepare(page, state):
            return LinkedInApplicationPageState(
                easy_apply=True,
                modal_open=True,
                modal_submit_visible=True,
            )

        async def fake_submit(page):
            return True

        async def fake_exception_result(exc, **kwargs):
            raise AssertionError("exception path should not run")

        async def fake_run_with_linkedin_page(*, storage_state_path, headless, page_operation):
            class _Page:
                async def goto(self, url, wait_until="domcontentloaded"):
                    return None

            return await page_operation(_Page())

        with patch(
            "job_hunter_agent.collectors.linkedin_application_submission_flow.run_with_linkedin_page",
            side_effect=fake_run_with_linkedin_page,
        ):
            result = asyncio.run(
                submit_linkedin_application(
                    job=job,
                    storage_state_path=Path("linkedin-state.json"),
                    headless=True,
                    ensure_target_job_page=fake_ensure,
                    read_state_with_hydration=fake_read,
                    capture_failure_artifacts=fake_capture,
                    prepare_submit_state=fake_prepare,
                    execution_submit=fake_submit,
                    format_modal_interpretation_for_error=lambda state: "",
                    build_submit_exception_result=fake_exception_result,
                )
            )

        self.assertEqual(result.status, "submitted")
        self.assertIn("submissao real concluida no LinkedIn", result.detail)
