import unittest

from job_hunter_agent.collectors.linkedin_application_review import (
    is_linkedin_review_final_available,
    is_linkedin_review_final_ready,
    is_linkedin_review_transition_available,
)
from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState


class LinkedInApplicationReviewTests(unittest.TestCase):
    def test_review_transition_available_when_review_button_visible_without_submit(self) -> None:
        state = LinkedInApplicationPageState(
            modal_open=True,
            modal_review_visible=True,
            modal_submit_visible=False,
        )

        self.assertTrue(is_linkedin_review_transition_available(state))

    def test_review_final_available_when_submit_visible_and_next_hidden(self) -> None:
        state = LinkedInApplicationPageState(
            modal_open=True,
            modal_submit_visible=True,
            modal_next_visible=False,
        )

        self.assertTrue(is_linkedin_review_final_available(state))

    def test_review_final_ready_requires_no_extra_blockers(self) -> None:
        blocked = LinkedInApplicationPageState(
            modal_open=True,
            modal_submit_visible=True,
            modal_next_visible=False,
            modal_questions_visible=True,
        )
        ready = LinkedInApplicationPageState(
            modal_open=True,
            modal_submit_visible=True,
            modal_next_visible=False,
        )

        self.assertFalse(is_linkedin_review_final_ready(blocked))
        self.assertTrue(is_linkedin_review_final_ready(ready))

    def test_review_final_ready_accepts_explicit_flag(self) -> None:
        state = LinkedInApplicationPageState(
            modal_open=True,
            ready_to_submit=True,
            modal_questions_visible=True,
        )

        self.assertTrue(is_linkedin_review_final_ready(state))
