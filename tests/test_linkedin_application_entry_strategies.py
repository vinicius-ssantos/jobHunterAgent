import asyncio
import unittest

from job_hunter_agent.collectors.linkedin_application_entry_strategies import (
    LinkedInApplyHrefEntrypointStrategy,
    LinkedInApplyHtmlRecoveryStrategy,
)
from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState


class LinkedInApplicationEntrypointStrategiesTests(unittest.TestCase):
    def test_href_entrypoint_opens_apply_route_and_inspects_modal(self) -> None:
        calls: list[str] = []

        async def extract_easy_apply_href(page):
            calls.append("extract")
            return "https://www.linkedin.com/jobs/view/123/apply/?openSDUIApplyFlow=true"

        async def prepare_job_page_for_apply(page):
            calls.append("prepare")

        async def read_page_state(page):
            calls.append("read")
            return LinkedInApplicationPageState(easy_apply=True, modal_open=True, modal_submit_visible=True)

        async def inspect_easy_apply_modal(page, state, close_modal):
            calls.append(f"inspect:{close_modal}")
            return LinkedInApplicationPageState(
                **{
                    **state.__dict__,
                    "ready_to_submit": True,
                }
            )

        def is_page_closed(page):
            return False

        class _Page:
            def __init__(self) -> None:
                self.navigated_to = ""

            async def goto(self, url, wait_until="domcontentloaded"):
                self.navigated_to = url

            async def wait_for_timeout(self, timeout):
                calls.append(f"wait:{timeout}")

        strategy = LinkedInApplyHrefEntrypointStrategy(
            extract_easy_apply_href=extract_easy_apply_href,
            prepare_job_page_for_apply=prepare_job_page_for_apply,
            read_page_state=read_page_state,
            inspect_easy_apply_modal=inspect_easy_apply_modal,
            is_page_closed=is_page_closed,
        )

        page = _Page()
        state = asyncio.run(strategy.open(page, close_modal=False))

        self.assertEqual(page.navigated_to, "https://www.linkedin.com/jobs/view/123/apply/?openSDUIApplyFlow=true")
        self.assertTrue(state.ready_to_submit)
        self.assertEqual(calls, ["extract", "wait:1800", "prepare", "read", "inspect:False"])

    def test_html_recovery_strategy_uses_hidden_internal_apply_metadata(self) -> None:
        class _Page:
            def __init__(self) -> None:
                self.navigated_to = ""

            async def content(self):
                return """
                <html><body>
                <code>{"onsiteApply":true,"applyCtaText":{"text":"Candidatura simplificada"},"companyApplyUrl":"https://www.linkedin.com/job-apply/4389607214"}</code>
                </body></html>
                """

            async def goto(self, url, wait_until="domcontentloaded"):
                self.navigated_to = url

            async def wait_for_timeout(self, timeout):
                return None

        strategy = LinkedInApplyHtmlRecoveryStrategy()
        page = _Page()

        recovered = asyncio.run(
            strategy.recover(
                page,
                job_url="https://www.linkedin.com/jobs/view/4389607214/",
            )
        )

        self.assertTrue(recovered)
        self.assertEqual(
            page.navigated_to,
            "https://www.linkedin.com/jobs/view/4389607214/apply/?openSDUIApplyFlow=true",
        )
