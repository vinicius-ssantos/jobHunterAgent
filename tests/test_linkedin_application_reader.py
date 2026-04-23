import unittest

from job_hunter_agent.collectors.linkedin_application_reader import (
    LINKEDIN_APPLICATION_PAGE_STATE_SCRIPT,
    LinkedInApplicationPageReader,
    normalize_linkedin_application_page_state_payload,
)
from job_hunter_agent.collectors.linkedin_application_state import (
    LinkedInApplicationOperationalSignals,
    LinkedInApplicationPageSignals,
)


class LinkedInApplicationReaderTests(unittest.TestCase):
    def test_script_contains_core_signals(self) -> None:
        self.assertIn("easy apply", LINKEDIN_APPLICATION_PAGE_STATE_SCRIPT.lower())
        self.assertIn("modal_submit_visible", LINKEDIN_APPLICATION_PAGE_STATE_SCRIPT)
        self.assertIn("saveApplicationDialogVisible", LINKEDIN_APPLICATION_PAGE_STATE_SCRIPT)

    def test_normalize_payload_converts_lists_to_tuples(self) -> None:
        state = normalize_linkedin_application_page_state_payload(
            {
                "current_url": "https://www.linkedin.com/jobs/view/123/",
                "easy_apply": True,
                "resumable_fields": ["email", "telefone"],
                "filled_fields": ["telefone"],
                "modal_headings": ["informacoes de contato"],
                "modal_buttons": ["next"],
                "modal_fields": ["email"],
                "modal_questions": ["autorizacao"],
                "answered_questions": ["java"],
                "unanswered_questions": ["ejb"],
            }
        )

        self.assertEqual(state.resumable_fields, ("email", "telefone"))
        self.assertEqual(state.filled_fields, ("telefone",))
        self.assertEqual(state.modal_headings, ("informacoes de contato",))
        self.assertEqual(state.answered_questions, ("java",))
        self.assertEqual(state.unanswered_questions, ("ejb",))

    def test_state_exposes_page_and_operational_signal_views(self) -> None:
        state = normalize_linkedin_application_page_state_payload(
            {
                "current_url": "https://www.linkedin.com/jobs/view/123/",
                "easy_apply": True,
                "modal_open": True,
                "modal_submit_visible": True,
                "modal_headings": ["review"],
                "resumable_fields": ["email"],
                "filled_fields": ["email"],
                "ready_to_submit": True,
                "answered_questions": ["java"],
            }
        )

        page = state.page_signals()
        progress = state.operational_signals()

        self.assertEqual(
            page,
            LinkedInApplicationPageSignals(
                current_url="https://www.linkedin.com/jobs/view/123/",
                easy_apply=True,
                modal_open=True,
                modal_submit_visible=True,
                modal_headings=("review",),
            ),
        )
        self.assertEqual(
            progress,
            LinkedInApplicationOperationalSignals(
                resumable_fields=("email",),
                filled_fields=("email",),
                ready_to_submit=True,
                answered_questions=("java",),
            ),
        )
        self.assertTrue(state.has_resumable_fields())
        self.assertTrue(state.has_any_filled_fields())

    def test_normalize_payload_filters_country_code_questions(self) -> None:
        state = normalize_linkedin_application_page_state_payload(
            {
                "current_url": "https://www.linkedin.com/jobs/view/123/",
                "easy_apply": True,
                "modal_questions": [
                    "Country code",
                    "C\u00f3digo do pa\u00eds",
                    "Years of experience with Java",
                ],
            }
        )

        self.assertEqual(state.modal_questions, ("Years of experience with Java",))

    def test_reader_evaluates_script_and_returns_state(self) -> None:
        class _Page:
            def __init__(self):
                self.script = ""

            async def evaluate(self, script):
                self.script = script
                return {
                    "current_url": "https://www.linkedin.com/jobs/view/123/",
                    "easy_apply": True,
                    "modal_open": False,
                    "resumable_fields": ["email"],
                }

        reader = LinkedInApplicationPageReader()

        import asyncio

        page = _Page()
        state = asyncio.run(reader.read(page))

        self.assertTrue(state.easy_apply)
        self.assertEqual(state.resumable_fields, ("email",))
        self.assertIn("easy apply", page.script.lower())
