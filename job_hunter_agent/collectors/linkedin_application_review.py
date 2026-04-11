from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState


def is_linkedin_review_transition_available(state: LinkedInApplicationPageState) -> bool:
    return state.modal_open and state.modal_review_visible and not state.modal_submit_visible


def is_linkedin_review_final_available(state: LinkedInApplicationPageState) -> bool:
    return state.modal_open and state.modal_submit_visible and not state.modal_next_visible


def is_linkedin_review_final_ready(state: LinkedInApplicationPageState) -> bool:
    return state.ready_to_submit or (
        is_linkedin_review_final_available(state)
        and not (
            state.modal_review_visible
            or state.modal_file_upload
            or state.modal_questions_visible
        )
    )
