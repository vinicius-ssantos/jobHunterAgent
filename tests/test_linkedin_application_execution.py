import asyncio
import unittest

from job_hunter_agent.collectors.linkedin_application_execution import LinkedInEasyApplyExecution
from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState


class LinkedInEasyApplyExecutionTests(unittest.TestCase):
    def test_inspect_preflight_state_tries_direct_url_when_modal_does_not_open(self) -> None:
        calls: list[str] = []

        async def inspect_easy_apply_modal(page, state, close_modal):
            calls.append(f"inspect:{close_modal}")
            return LinkedInApplicationPageState(easy_apply=True, modal_open=True, modal_submit_visible=True)

        async def try_submit_application(page):
            raise AssertionError("nao deveria submeter no preflight")

        execution = LinkedInEasyApplyExecution(
            inspect_easy_apply_modal=inspect_easy_apply_modal,
            try_submit_application=try_submit_application,
        )

        state = asyncio.run(
            execution.inspect_preflight_state(
                object(),
                LinkedInApplicationPageState(easy_apply=True, modal_open=False),
            )
        )

        self.assertTrue(state.modal_open)
        self.assertEqual(calls, ["inspect:True"])

    def test_prepare_submit_state_uses_inspection_pipeline(self) -> None:
        calls: list[str] = []

        async def inspect_easy_apply_modal(page, state, close_modal):
            calls.append(f"inspect:{state.modal_open}:{close_modal}")
            return LinkedInApplicationPageState(easy_apply=True, modal_open=True, modal_submit_visible=True)

        async def try_submit_application(page):
            raise AssertionError("nao deveria submeter durante preparacao")

        execution = LinkedInEasyApplyExecution(
            inspect_easy_apply_modal=inspect_easy_apply_modal,
            try_submit_application=try_submit_application,
        )

        state = asyncio.run(
            execution.prepare_submit_state(
                object(),
                LinkedInApplicationPageState(easy_apply=True, modal_open=False),
            )
        )

        self.assertTrue(state.modal_open)
        self.assertEqual(calls, ["inspect:False:False"])
