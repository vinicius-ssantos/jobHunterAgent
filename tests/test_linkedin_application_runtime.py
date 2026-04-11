from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from job_hunter_agent.collectors.linkedin_application_runtime import (
    run_linkedin_async,
    run_with_linkedin_page,
)


class LinkedInApplicationRuntimeTests(unittest.TestCase):
    def test_run_linkedin_async_executes_coroutine(self) -> None:
        async def _sample() -> str:
            return "ok"

        result = run_linkedin_async(_sample())

        self.assertEqual(result, "ok")

    def test_run_with_linkedin_page_bootstraps_browser_context_and_page(self) -> None:
        events: list[str] = []

        class _Page:
            pass

        class _Context:
            def __init__(self) -> None:
                self.page = _Page()

            async def new_page(self):
                events.append("new_page")
                return self.page

            async def close(self):
                events.append("context_close")

        class _Browser:
            def __init__(self) -> None:
                self.context = _Context()

            async def new_context(self, storage_state=None):
                events.append(f"new_context:{storage_state}")
                return self.context

            async def close(self):
                events.append("browser_close")

        class _Chromium:
            async def launch(self, executable_path=None, headless=None, args=None):
                events.append(f"launch:{headless}:{args}")
                return _Browser()

        class _PlaywrightManager:
            def __init__(self) -> None:
                self.chromium = _Chromium()

            async def __aenter__(self):
                events.append("playwright_enter")
                return self

            async def __aexit__(self, exc_type, exc, tb):
                events.append("playwright_exit")

        fake_async_api = types.SimpleNamespace(async_playwright=lambda: _PlaywrightManager())
        previous_module = sys.modules.get("playwright.async_api")
        sys.modules["playwright.async_api"] = fake_async_api
        try:
            with patch(
                "job_hunter_agent.collectors.linkedin_application_runtime.resolve_local_chromium",
                return_value=Path("/tmp/chromium"),
            ), patch(
                "job_hunter_agent.collectors.linkedin_application_runtime.load_playwright_storage_state",
                return_value={"cookies": []},
            ):
                async def _operation(page) -> str:
                    events.append(f"operate:{type(page).__name__}")
                    return "done"

                result = run_linkedin_async(
                    run_with_linkedin_page(
                        storage_state_path=Path("linkedin-state.json"),
                        headless=True,
                        page_operation=_operation,
                    )
                )
        finally:
            if previous_module is None:
                sys.modules.pop("playwright.async_api", None)
            else:
                sys.modules["playwright.async_api"] = previous_module

        self.assertEqual(result, "done")
        self.assertIn("playwright_enter", events)
        self.assertIn("new_page", events)
        self.assertIn("operate:_Page", events)
        self.assertIn("context_close", events)
        self.assertIn("browser_close", events)
        self.assertIn("playwright_exit", events)
