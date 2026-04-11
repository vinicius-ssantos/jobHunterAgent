import unittest

from job_hunter_agent.collectors.linkedin_application_opening import LinkedInEasyApplyFlowOpener
from job_hunter_agent.collectors.linkedin_application_state import (
    LinkedInApplicationPageState,
    LinkedInJobPageReadiness,
)


class LinkedInEasyApplyFlowOpenerTests(unittest.TestCase):
    def _build_opener(
        self,
        *,
        prepare_job_page_for_apply,
        read_page_state,
        assess_job_page_readiness,
        extract_easy_apply_href,
        inspect_easy_apply_modal,
        is_page_closed,
    ) -> LinkedInEasyApplyFlowOpener:
        return LinkedInEasyApplyFlowOpener(
            prepare_job_page_for_apply=prepare_job_page_for_apply,
            read_page_state=read_page_state,
            assess_job_page_readiness=assess_job_page_readiness,
            extract_easy_apply_href=extract_easy_apply_href,
            inspect_easy_apply_modal=inspect_easy_apply_modal,
            is_page_closed=is_page_closed,
        )

    def test_try_open_easy_apply_via_direct_url_reads_apply_route_when_modal_does_not_open(self) -> None:
        class _Page:
            def __init__(self):
                self.navigated_to = ""

            async def goto(self, url, wait_until="domcontentloaded"):
                self.navigated_to = url

            async def wait_for_timeout(self, timeout):
                return None

        async def fake_extract(page):
            return "https://www.linkedin.com/jobs/view/123/apply/?openSDUIApplyFlow=true"

        async def fake_prepare(page):
            return None

        async def fake_read(page):
            return LinkedInApplicationPageState(
                current_url="https://www.linkedin.com/jobs/view/123/apply/?openSDUIApplyFlow=true",
                easy_apply=True,
                modal_open=False,
            )

        async def fake_inspect(page, initial_state, close_modal):
            return initial_state

        opener = self._build_opener(
            prepare_job_page_for_apply=fake_prepare,
            read_page_state=fake_read,
            assess_job_page_readiness=lambda job, state: LinkedInJobPageReadiness("ready", "ok", state.sample),
            extract_easy_apply_href=fake_extract,
            inspect_easy_apply_modal=fake_inspect,
            is_page_closed=lambda page: False,
        )

        import asyncio

        page = _Page()
        state = asyncio.run(opener.try_open_easy_apply_via_direct_url(page, close_modal=False))

        self.assertEqual(page.navigated_to, "https://www.linkedin.com/jobs/view/123/apply/?openSDUIApplyFlow=true")
        self.assertTrue(state.easy_apply)

    def test_try_open_easy_apply_via_direct_url_inspects_modal_when_route_opens_dialog(self) -> None:
        class _Page:
            async def goto(self, url, wait_until="domcontentloaded"):
                return None

            async def wait_for_timeout(self, timeout):
                return None

        async def fake_extract(page):
            return "https://www.linkedin.com/jobs/view/123/apply/?openSDUIApplyFlow=true"

        async def fake_prepare(page):
            return None

        async def fake_read(page):
            return LinkedInApplicationPageState(
                current_url="https://www.linkedin.com/jobs/view/123/apply/?openSDUIApplyFlow=true",
                easy_apply=True,
                modal_open=True,
            )

        async def fake_inspect(page, initial_state, close_modal):
            return LinkedInApplicationPageState(
                **{**initial_state.__dict__, "ready_to_submit": True}
            )

        opener = self._build_opener(
            prepare_job_page_for_apply=fake_prepare,
            read_page_state=fake_read,
            assess_job_page_readiness=lambda job, state: LinkedInJobPageReadiness("ready", "ok", state.sample),
            extract_easy_apply_href=fake_extract,
            inspect_easy_apply_modal=fake_inspect,
            is_page_closed=lambda page: False,
        )

        import asyncio

        state = asyncio.run(opener.try_open_easy_apply_via_direct_url(_Page(), close_modal=False))

        self.assertTrue(state.modal_open)
        self.assertTrue(state.ready_to_submit)

    def test_recover_easy_apply_from_page_html_uses_hidden_internal_apply_metadata(self) -> None:
        class _Page:
            def __init__(self):
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

        opener = self._build_opener(
            prepare_job_page_for_apply=lambda page: None,
            read_page_state=lambda page: None,
            assess_job_page_readiness=lambda job, state: LinkedInJobPageReadiness("ready", "ok", state.sample),
            extract_easy_apply_href=lambda page: "",
            inspect_easy_apply_modal=lambda page, initial_state, close_modal: initial_state,
            is_page_closed=lambda page: False,
        )

        import asyncio

        page = _Page()
        recovered = asyncio.run(
            opener.recover_easy_apply_from_page_html(
                page,
                type("Job", (), {"url": "https://www.linkedin.com/jobs/view/4389607214/"})(),
            )
        )

        self.assertTrue(recovered)
        self.assertEqual(
            page.navigated_to,
            "https://www.linkedin.com/jobs/view/4389607214/apply/?openSDUIApplyFlow=true",
        )

    def test_read_state_with_hydration_retries_before_declaring_no_apply_cta(self) -> None:
        class _Page:
            async def wait_for_timeout(self, timeout):
                return None

            async def wait_for_load_state(self, state):
                return None

        calls = {"count": 0}

        async def fake_prepare(page):
            return None

        async def fake_read(page):
            calls["count"] += 1
            if calls["count"] == 1:
                return LinkedInApplicationPageState(
                    current_url="https://www.linkedin.com/jobs/view/4389607214/",
                )
            return LinkedInApplicationPageState(
                current_url="https://www.linkedin.com/jobs/view/4389607214/",
                easy_apply=True,
                cta_text="candidatura simplificada",
            )

        async def fake_extract(page):
            return ""

        async def fake_inspect(page, initial_state, close_modal):
            return initial_state

        readiness_calls = {"count": 0}

        def fake_assess(job, state):
            readiness_calls["count"] += 1
            if state.easy_apply:
                return LinkedInJobPageReadiness("ready", "ok", state.sample)
            return LinkedInJobPageReadiness("no_apply_cta", "sem cta", state.sample)

        opener = self._build_opener(
            prepare_job_page_for_apply=fake_prepare,
            read_page_state=fake_read,
            assess_job_page_readiness=fake_assess,
            extract_easy_apply_href=fake_extract,
            inspect_easy_apply_modal=fake_inspect,
            is_page_closed=lambda page: False,
        )
        opener.recover_easy_apply_from_page_html = fake_extract

        import asyncio

        state, readiness = asyncio.run(
            opener.read_state_with_hydration(
                _Page(),
                type("Job", (), {"url": "https://www.linkedin.com/jobs/view/4389607214/"})(),
            )
        )

        self.assertEqual(calls["count"], 2)
        self.assertEqual(readiness_calls["count"], 2)
        self.assertTrue(state.easy_apply)
        self.assertEqual(readiness.result, "ready")
