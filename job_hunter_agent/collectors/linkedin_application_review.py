from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState


@dataclass(frozen=True)
class LinkedInReviewFinalStrategy:
    def is_transition_available(self, state: "LinkedInApplicationPageState") -> bool:
        page = state.page_signals()
        return page.modal_open and page.modal_review_visible and not page.modal_submit_visible

    def is_final_available(self, state: "LinkedInApplicationPageState") -> bool:
        page = state.page_signals()
        return page.modal_open and page.modal_submit_visible and not page.modal_next_visible

    def is_final_ready(self, state: "LinkedInApplicationPageState") -> bool:
        page = state.page_signals()
        progress = state.operational_signals()
        return progress.ready_to_submit or (
            self.is_final_available(state)
            and not (
                page.modal_review_visible
                or page.modal_file_upload
                or page.modal_questions_visible
            )
        )


DEFAULT_LINKEDIN_REVIEW_FINAL_STRATEGY = LinkedInReviewFinalStrategy()


def is_linkedin_review_transition_available(state: LinkedInApplicationPageState) -> bool:
    return DEFAULT_LINKEDIN_REVIEW_FINAL_STRATEGY.is_transition_available(state)


def is_linkedin_review_final_available(state: LinkedInApplicationPageState) -> bool:
    return DEFAULT_LINKEDIN_REVIEW_FINAL_STRATEGY.is_final_available(state)


def is_linkedin_review_final_ready(state: LinkedInApplicationPageState) -> bool:
    return DEFAULT_LINKEDIN_REVIEW_FINAL_STRATEGY.is_final_ready(state)
