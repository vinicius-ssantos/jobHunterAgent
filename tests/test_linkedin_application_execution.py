import asyncio
import unittest

from job_hunter_agent.collectors.linkedin_application_execution import LinkedInEasyApplyExecution
from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState


class LinkedInEasyApplyExecutionTests(unittest.TestCase):
    def test_inspect_preflight_state_tries_direct_url_when_modal_does_not_open(self) -> None:
        calls: list[str] = []

        async def inspect_easy_apply_modal(page, state, close_modal):
            calls.append(f"inspect:{close_modal}")
            return LinkedInApplicationPageState(easy_apply=True, modal_open=False)

        async def try_open_easy_apply_modal(page):
            raise AssertionError("nao deveria abrir modal diretamente no preflight")

        async def try_open_easy_apply_via_direct_url(page, close_modal):
            calls.append(f"direct:{close_modal}")
            return LinkedInApplicationPageState(easy_apply=True, modal_open=True, modal_submit_visible=True)

        async def try_submit_application(page):
            raise AssertionError("nao deveria submeter no preflight")

        async def read_page_state(page):
            raise AssertionError("nao deveria reler pagina no preflight")

        execution = LinkedInEasyApplyExecution(
            inspect_easy_apply_modal=inspect_easy_apply_modal,
            try_open_easy_apply_modal=try_open_easy_apply_modal,
            try_open_easy_apply_via_direct_url=try_open_easy_apply_via_direct_url,
            try_submit_application=try_submit_application,
            read_page_state=read_page_state,
        )

        state = asyncio.run(
            execution.inspect_preflight_state(
                object(),
                LinkedInApplicationPageState(easy_apply=True, modal_open=False),
            )
        )

        self.assertTrue(state.modal_open)
        self.assertEqual(calls, ["inspect:True", "direct:True"])

    def test_prepare_submit_state_retries_modal_open_before_direct_url(self) -> None:
        calls: list[str] = []

        async def inspect_easy_apply_modal(page, state, close_modal):
            calls.append(f"inspect:{state.modal_open}:{close_modal}")
            return state

        async def try_open_easy_apply_modal(page):
            calls.append("open-modal")
            return True

        async def try_open_easy_apply_via_direct_url(page, close_modal):
            calls.append(f"direct:{close_modal}")
            return LinkedInApplicationPageState(easy_apply=True, modal_open=True, modal_submit_visible=True)

        async def try_submit_application(page):
            raise AssertionError("nao deveria submeter durante preparacao")

        async def read_page_state(page):
            calls.append("read")
            return LinkedInApplicationPageState(easy_apply=True, modal_open=False)

        class _Page:
            async def wait_for_timeout(self, timeout):
                calls.append(f"wait:{timeout}")

        execution = LinkedInEasyApplyExecution(
            inspect_easy_apply_modal=inspect_easy_apply_modal,
            try_open_easy_apply_modal=try_open_easy_apply_modal,
            try_open_easy_apply_via_direct_url=try_open_easy_apply_via_direct_url,
            try_submit_application=try_submit_application,
            read_page_state=read_page_state,
        )

        state = asyncio.run(
            execution.prepare_submit_state(
                _Page(),
                LinkedInApplicationPageState(easy_apply=True, modal_open=False),
            )
        )

        self.assertTrue(state.modal_open)
        self.assertEqual(
            calls,
            ["inspect:False:False", "open-modal", "wait:1800", "read", "direct:False"],
        )
