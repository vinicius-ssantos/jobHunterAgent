from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Callable

from pathlib import Path

from job_hunter_agent.collectors.linkedin_application_fields import LinkedInEasyApplyFieldFiller
from job_hunter_agent.collectors.linkedin_application_review import (
    is_linkedin_review_final_available,
    is_linkedin_review_transition_available,
)
from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState

MODAL_OPEN_WAIT_MS = 2500
FIELD_FILL_WAIT_MS = 1200
UPLOAD_WAIT_MS = 1800
NEXT_STEP_WAIT_MS = 2200
BUTTON_CLICK_WAIT_MS = 1200
MODAL_CLOSE_WAIT_MS = 500
SUBMIT_WAIT_MS = 2500


@dataclass(frozen=True)
class LinkedInModalProgress:
    filled_fields: tuple[str, ...] = ()
    answered_questions: tuple[str, ...] = ()
    unanswered_questions: tuple[str, ...] = ()
    progressed_to_next_step: bool = False
    uploaded_resume: bool = False
    reached_review_step: bool = False
    ready_to_submit: bool = False


class LinkedInEasyApplyModalDriver:
    def __init__(
        self,
        *,
        resume_path: Path | None,
        contact_email: str,
        phone: str,
        phone_country_code: str,
        candidate_profile: CandidateProfile | None = None,
        candidate_profile_path: Path | None = None,
        modal_interpreter: Callable[[LinkedInApplicationPageState], object] | None = None,
    ) -> None:
        self.resume_path = resume_path
        self.contact_email = contact_email
        self.phone = phone
        self.phone_country_code = phone_country_code
        self.candidate_profile = candidate_profile
        self.candidate_profile_path = candidate_profile_path
        self.modal_interpreter = modal_interpreter
        self._field_filler = LinkedInEasyApplyFieldFiller(
            contact_email=self.contact_email,
            phone=self.phone,
            phone_country_code=self.phone_country_code,
            candidate_profile=self.candidate_profile,
            candidate_profile_path=self.candidate_profile_path,
        )

    async def inspect_easy_apply_modal(
        self,
        page,
        *,
        initial_state: LinkedInApplicationPageState,
        read_page_state,
        try_open_easy_apply_modal,
        close_modal: bool = True,
    ) -> LinkedInApplicationPageState:
        state = initial_state
        opened = False
        for _ in range(2):
            await try_open_easy_apply_modal(page)
            await page.wait_for_timeout(MODAL_OPEN_WAIT_MS)
            state = await read_page_state(page)
            if state.modal_open:
                opened = True
                break
        if not opened:
            return state
        return await self.inspect_open_easy_apply_modal(
            page,
            state,
            read_page_state=read_page_state,
            close_modal=close_modal,
        )

    async def inspect_open_easy_apply_modal(
        self,
        page,
        initial_state: LinkedInApplicationPageState,
        *,
        read_page_state,
        close_modal: bool = True,
    ) -> LinkedInApplicationPageState:
        state = initial_state
        progress = LinkedInModalProgress()

        for _ in range(5):
            state, progress = await self._collect_modal_progress(page, state, read_page_state, progress)
            if is_linkedin_review_final_available(state):
                progress = replace(progress, ready_to_submit=True)
                break

            state, progress, moved = await self._advance_modal_flow(page, state, read_page_state, progress)
            if is_linkedin_review_final_available(state):
                progress = replace(progress, ready_to_submit=True)
                break
            if not moved:
                break

        state = self._merge_progress_into_state(state, progress)
        if close_modal:
            await self.try_close_modal(page)
        return state

    def interpret_modal_state(self, state: LinkedInApplicationPageState):
        if self.modal_interpreter is None:
            from job_hunter_agent.collectors.linkedin_modal_llm import deterministic_interpret_linkedin_modal

            return deterministic_interpret_linkedin_modal(state)
        try:
            return self.modal_interpreter(state)
        except Exception:
            from job_hunter_agent.collectors.linkedin_modal_llm import deterministic_interpret_linkedin_modal

            return deterministic_interpret_linkedin_modal(state)

    def format_modal_interpretation_for_error(self, state: LinkedInApplicationPageState) -> str:
        if not state.modal_open:
            return ""
        try:
            from job_hunter_agent.collectors.linkedin_modal_llm import format_linkedin_modal_interpretation

            interpretation = self.interpret_modal_state(state)
            return f" | {format_linkedin_modal_interpretation(interpretation)}"
        except Exception:
            return ""

    async def try_fill_safe_fields(self, page) -> tuple[str, ...]:
        return await self._field_filler.try_fill_safe_fields(page)

    async def try_fill_supported_profile_answers(
        self,
        page,
        state: LinkedInApplicationPageState,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        return await self._field_filler.try_fill_supported_profile_answers(page, state)

    def record_pending_questions(self, questions: tuple[str, ...]) -> None:
        self._field_filler.record_pending_questions(questions)

    async def try_advance_single_step(self, page) -> bool:
        return await self._click_first_available_button(
            page,
            [
                page.get_by_role(
                    "button",
                    name=re.compile(r"(next|continuar|avancar|avançar|avanÃƒÂ§ar)", re.IGNORECASE),
                ).first,
                page.locator('[role="dialog"] button').filter(
                    has_text=re.compile(r"(next|continuar|avancar|avançar|avanÃƒÂ§ar)", re.IGNORECASE)
                ).first,
            ],
            wait_after_click_ms=BUTTON_CLICK_WAIT_MS,
        )

    async def try_upload_resume(self, page) -> bool:
        if self.resume_path is None or not self.resume_path.exists():
            return False
        candidates = [
            page.locator('[role="dialog"] input[type="file"]').first,
            page.locator('input[type="file"]').first,
        ]
        for candidate in candidates:
            try:
                if await candidate.count() == 0:
                    continue
                await candidate.set_input_files(str(self.resume_path))
                return True
            except Exception:
                continue
        return False

    async def try_open_review_step(self, page) -> bool:
        return await self._click_first_available_button(
            page,
            [
                page.get_by_role(
                    "button",
                    name=re.compile(r"(review|revisar)", re.IGNORECASE),
                ).first,
                page.locator('[role="dialog"] button').filter(
                    has_text=re.compile(r"(review|revisar)", re.IGNORECASE)
                ).first,
            ],
            wait_after_click_ms=BUTTON_CLICK_WAIT_MS,
        )

    async def try_close_modal(self, page) -> None:
        if await page.locator('[role="dialog"]').count() == 0:
            return
        await self._click_first_available_button(
            page,
            [
                page.get_by_role(
                    "button",
                    name=re.compile(r"(dismiss|close|fechar|cancel|cancelar|descartar)", re.IGNORECASE),
                ).first,
                page.locator(
                    '[role="dialog"] button[aria-label*="Dismiss"], [role="dialog"] button[aria-label*="Close"]'
                ).first,
            ],
            wait_after_click_ms=MODAL_CLOSE_WAIT_MS,
        )

    async def try_submit_application(self, page) -> bool:
        clicked = await self._click_first_available_button(
            page,
            [
                page.get_by_role(
                    "button",
                    name=re.compile(r"(submit application|enviar candidatura)", re.IGNORECASE),
                ).first,
                page.locator('[role="dialog"] button').filter(
                    has_text=re.compile(r"(submit application|enviar candidatura)", re.IGNORECASE)
                ).first,
            ],
            click_timeout_ms=4000,
            wait_after_click_ms=SUBMIT_WAIT_MS,
        )
        if not clicked:
            return False
        return await self.detect_submit_success(page)

    async def detect_submit_success(self, page) -> bool:
        try:
            return bool(
                await page.evaluate(
                    """
                    () => {
                      const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
                      const bodyText = normalize(document.body.innerText || "");
                      const successHints = [
                        "application submitted",
                        "candidatura enviada",
                        "your application was sent",
                        "sua candidatura foi enviada",
                      ];
                      if (successHints.some((hint) => bodyText.includes(hint))) {
                        return true;
                      }
                      return document.querySelector('[role="dialog"]') === null;
                    }
                    """
                )
            )
        except Exception:
            return False

    async def _collect_modal_progress(
        self,
        page,
        state: LinkedInApplicationPageState,
        read_page_state,
        progress: LinkedInModalProgress,
    ) -> tuple[LinkedInApplicationPageState, LinkedInModalProgress]:
        filled_fields = await self.try_fill_safe_fields(page)
        if filled_fields:
            progress = replace(
                progress,
                filled_fields=self._merge_names(progress.filled_fields, filled_fields),
            )
            await page.wait_for_timeout(FIELD_FILL_WAIT_MS)
        state = await read_page_state(page)
        answered_questions, unanswered_questions = await self.try_fill_supported_profile_answers(page, state)
        if answered_questions:
            progress = replace(
                progress,
                answered_questions=self._merge_names(progress.answered_questions, answered_questions),
            )
            await page.wait_for_timeout(FIELD_FILL_WAIT_MS)
            state = await read_page_state(page)
        if unanswered_questions:
            progress = replace(
                progress,
                unanswered_questions=self._merge_names(progress.unanswered_questions, unanswered_questions),
            )
            self.record_pending_questions(unanswered_questions)
        return self._merge_progress_into_state(state, progress), progress

    async def _advance_modal_flow(
        self,
        page,
        state: LinkedInApplicationPageState,
        read_page_state,
        progress: LinkedInModalProgress,
    ) -> tuple[LinkedInApplicationPageState, LinkedInModalProgress, bool]:
        interpretation = self.interpret_modal_state(state)
        action = interpretation.recommended_action
        if action == "submit_if_authorized" and is_linkedin_review_final_available(state):
            return state, replace(progress, ready_to_submit=True), False
        if action == "upload_resume" and state.modal_open and state.modal_file_upload and not progress.uploaded_resume:
            return await self._attempt_resume_upload(page, state, read_page_state, progress)
        if action == "open_review" and is_linkedin_review_transition_available(state):
            return await self._attempt_open_review(page, state, read_page_state, progress)
        if action == "click_next" and state.modal_open and state.modal_next_visible and not state.modal_submit_visible:
            return await self._attempt_next_step(page, state, read_page_state, progress)
        if state.modal_open and state.modal_file_upload and not progress.uploaded_resume:
            return await self._attempt_resume_upload(page, state, read_page_state, progress)
        if is_linkedin_review_transition_available(state):
            return await self._attempt_open_review(page, state, read_page_state, progress)
        if state.modal_open and state.modal_next_visible and not state.modal_submit_visible:
            return await self._attempt_next_step(page, state, read_page_state, progress)
        return state, progress, False

    async def _attempt_resume_upload(
        self,
        page,
        state: LinkedInApplicationPageState,
        read_page_state,
        progress: LinkedInModalProgress,
    ) -> tuple[LinkedInApplicationPageState, LinkedInModalProgress, bool]:
        uploaded_resume = await self.try_upload_resume(page)
        if not uploaded_resume:
            return state, progress, False
        await page.wait_for_timeout(UPLOAD_WAIT_MS)
        return await self._read_state_after_modal_action(
            page,
            read_page_state,
            replace(progress, uploaded_resume=True),
        )

    async def _attempt_open_review(
        self,
        page,
        state: LinkedInApplicationPageState,
        read_page_state,
        progress: LinkedInModalProgress,
    ) -> tuple[LinkedInApplicationPageState, LinkedInModalProgress, bool]:
        review_opened = await self.try_open_review_step(page)
        if not review_opened:
            return state, progress, False
        await page.wait_for_timeout(UPLOAD_WAIT_MS)
        return await self._read_state_after_modal_action(
            page,
            read_page_state,
            replace(progress, reached_review_step=True),
        )

    async def _attempt_next_step(
        self,
        page,
        state: LinkedInApplicationPageState,
        read_page_state,
        progress: LinkedInModalProgress,
    ) -> tuple[LinkedInApplicationPageState, LinkedInModalProgress, bool]:
        next_progressed = await self.try_advance_single_step(page)
        if not next_progressed:
            return state, progress, False
        await page.wait_for_timeout(NEXT_STEP_WAIT_MS)
        return await self._read_state_after_modal_action(
            page,
            read_page_state,
            replace(progress, progressed_to_next_step=True),
        )

    async def _read_state_after_modal_action(
        self,
        page,
        read_page_state,
        progress: LinkedInModalProgress,
    ) -> tuple[LinkedInApplicationPageState, LinkedInModalProgress, bool]:
        state = await read_page_state(page)
        return state, progress, True

    def _merge_progress_into_state(
        self,
        state: LinkedInApplicationPageState,
        progress: LinkedInModalProgress,
    ) -> LinkedInApplicationPageState:
        return replace(
            state,
            filled_fields=self._merge_names(state.filled_fields, progress.filled_fields),
            answered_questions=self._merge_names(state.answered_questions, progress.answered_questions),
            unanswered_questions=self._merge_names(state.unanswered_questions, progress.unanswered_questions),
            progressed_to_next_step=state.progressed_to_next_step or progress.progressed_to_next_step,
            uploaded_resume=state.uploaded_resume or progress.uploaded_resume,
            reached_review_step=state.reached_review_step or progress.reached_review_step,
            ready_to_submit=state.ready_to_submit or progress.ready_to_submit,
        )

    @staticmethod
    def _merge_names(current: tuple[str, ...], new_items: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*current, *new_items)))

    async def _click_first_available_button(
        self,
        page,
        candidates,
        *,
        click_timeout_ms: int = 3000,
        wait_after_click_ms: int = 0,
    ) -> bool:
        for candidate in candidates:
            try:
                if await candidate.count() == 0:
                    continue
                await candidate.scroll_into_view_if_needed()
                await candidate.click(timeout=click_timeout_ms, force=True)
                if wait_after_click_ms:
                    await page.wait_for_timeout(wait_after_click_ms)
                return True
            except Exception:
                continue
        return False


