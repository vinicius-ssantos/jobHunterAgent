from __future__ import annotations

import re
from typing import Callable

from pathlib import Path

from job_hunter_agent.collectors.linkedin_application_fields import LinkedInEasyApplyFieldFiller
from job_hunter_agent.collectors.linkedin_application_review import (
    is_linkedin_review_final_available,
    is_linkedin_review_transition_available,
)
from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState


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
            await page.wait_for_timeout(2500)
            state = await read_page_state(page)
            if state.modal_open:
                opened = True
                break
        if not opened:
            return state

        all_filled_fields: tuple[str, ...] = ()
        all_answered_questions: tuple[str, ...] = ()
        all_unanswered_questions: tuple[str, ...] = ()
        progressed = False
        uploaded_resume = False
        reached_review_step = False
        ready_to_submit = False

        for _ in range(5):
            filled_fields = await self.try_fill_safe_fields(page)
            if filled_fields:
                all_filled_fields = tuple(dict.fromkeys((*all_filled_fields, *filled_fields)))
                await page.wait_for_timeout(1200)
            state = await read_page_state(page)
            answered_questions, unanswered_questions = await self.try_fill_supported_profile_answers(page, state)
            if answered_questions:
                all_answered_questions = tuple(dict.fromkeys((*all_answered_questions, *answered_questions)))
                await page.wait_for_timeout(1200)
                state = await read_page_state(page)
            if unanswered_questions:
                all_unanswered_questions = tuple(dict.fromkeys((*all_unanswered_questions, *unanswered_questions)))
                self.record_pending_questions(unanswered_questions)
            if all_filled_fields:
                state = LinkedInApplicationPageState(
                    **{
                        **state.__dict__,
                        "filled_fields": tuple(dict.fromkeys((*state.filled_fields, *all_filled_fields))),
                    }
                )
            if all_answered_questions or all_unanswered_questions:
                state = LinkedInApplicationPageState(
                    **{
                        **state.__dict__,
                        "answered_questions": tuple(dict.fromkeys((*state.answered_questions, *all_answered_questions))),
                        "unanswered_questions": tuple(dict.fromkeys((*state.unanswered_questions, *all_unanswered_questions))),
                    }
                )

            if is_linkedin_review_final_available(state):
                ready_to_submit = True
                break

            moved = False
            interpretation = self.interpret_modal_state(state)
            action = interpretation.recommended_action
            if action == "submit_if_authorized" and is_linkedin_review_final_available(state):
                ready_to_submit = True
                break
            if action == "upload_resume" and state.modal_open and state.modal_file_upload and not uploaded_resume:
                uploaded_resume = await self.try_upload_resume(page)
                if uploaded_resume:
                    moved = True
                    await page.wait_for_timeout(1800)
                    state = await read_page_state(page)
            elif action == "open_review" and is_linkedin_review_transition_available(state):
                review_opened = await self.try_open_review_step(page)
                if review_opened:
                    reached_review_step = True
                    moved = True
                    await page.wait_for_timeout(1800)
                    state = await read_page_state(page)
            elif action == "click_next" and state.modal_open and state.modal_next_visible and not state.modal_submit_visible:
                next_progressed = await self.try_advance_single_step(page)
                if next_progressed:
                    progressed = True
                    moved = True
                    await page.wait_for_timeout(2200)
                    state = await read_page_state(page)
            elif state.modal_open and state.modal_file_upload and not uploaded_resume:
                uploaded_resume = await self.try_upload_resume(page)
                if uploaded_resume:
                    moved = True
                    await page.wait_for_timeout(1800)
                    state = await read_page_state(page)
            elif is_linkedin_review_transition_available(state):
                review_opened = await self.try_open_review_step(page)
                if review_opened:
                    reached_review_step = True
                    moved = True
                    await page.wait_for_timeout(1800)
                    state = await read_page_state(page)
            elif state.modal_open and state.modal_next_visible and not state.modal_submit_visible:
                next_progressed = await self.try_advance_single_step(page)
                if next_progressed:
                    progressed = True
                    moved = True
                    await page.wait_for_timeout(2200)
                    state = await read_page_state(page)

            if is_linkedin_review_final_available(state):
                ready_to_submit = True
                break
            if not moved:
                break

        if progressed:
            state = LinkedInApplicationPageState(
                **{
                    **state.__dict__,
                    "filled_fields": tuple(dict.fromkeys((*state.filled_fields, *all_filled_fields))),
                    "progressed_to_next_step": True,
                }
            )
        elif all_filled_fields:
            state = LinkedInApplicationPageState(
                **{
                    **state.__dict__,
                    "filled_fields": tuple(dict.fromkeys((*state.filled_fields, *all_filled_fields))),
                }
            )
        if uploaded_resume:
            state = LinkedInApplicationPageState(
                **{
                    **state.__dict__,
                    "uploaded_resume": True,
                }
            )
        if reached_review_step:
            state = LinkedInApplicationPageState(
                **{
                    **state.__dict__,
                    "reached_review_step": True,
                }
            )
        if ready_to_submit:
            state = LinkedInApplicationPageState(
                **{
                    **state.__dict__,
                    "ready_to_submit": True,
                }
            )
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
        candidates = [
            page.get_by_role(
                "button",
                name=re.compile(r"(next|continuar|avancar|avançar|avanÃƒÂ§ar)", re.IGNORECASE),
            ).first,
            page.locator('[role="dialog"] button').filter(
                has_text=re.compile(r"(next|continuar|avancar|avançar|avanÃƒÂ§ar)", re.IGNORECASE)
            ).first,
        ]
        for candidate in candidates:
            try:
                if await candidate.count() == 0:
                    continue
                await candidate.scroll_into_view_if_needed()
                await candidate.click(timeout=3000, force=True)
                await page.wait_for_timeout(1200)
                return True
            except Exception:
                continue
        return False

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
        candidates = [
            page.get_by_role(
                "button",
                name=re.compile(r"(review|revisar)", re.IGNORECASE),
            ).first,
            page.locator('[role="dialog"] button').filter(
                has_text=re.compile(r"(review|revisar)", re.IGNORECASE)
            ).first,
        ]
        for candidate in candidates:
            try:
                if await candidate.count() == 0:
                    continue
                await candidate.scroll_into_view_if_needed()
                await candidate.click(timeout=3000, force=True)
                await page.wait_for_timeout(1200)
                return True
            except Exception:
                continue
        return False

    async def try_close_modal(self, page) -> None:
        if await page.locator('[role="dialog"]').count() == 0:
            return
        candidates = [
            page.get_by_role("button", name=re.compile(r"(dismiss|close|fechar|cancel|cancelar|descartar)", re.IGNORECASE)).first,
            page.locator('[role="dialog"] button[aria-label*="Dismiss"], [role="dialog"] button[aria-label*="Close"]').first,
        ]
        for candidate in candidates:
            try:
                if await candidate.count() > 0:
                    await candidate.click()
                    await page.wait_for_timeout(500)
                    return
            except Exception:
                continue

    async def try_submit_application(self, page) -> bool:
        candidates = [
            page.get_by_role(
                "button",
                name=re.compile(r"(submit application|enviar candidatura)", re.IGNORECASE),
            ).first,
            page.locator('[role="dialog"] button').filter(
                has_text=re.compile(r"(submit application|enviar candidatura)", re.IGNORECASE)
            ).first,
        ]
        for candidate in candidates:
            try:
                if await candidate.count() == 0:
                    continue
                await candidate.scroll_into_view_if_needed()
                await candidate.click(timeout=4000, force=True)
                await page.wait_for_timeout(2500)
                if await self.detect_submit_success(page):
                    return True
            except Exception:
                continue
        return False

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


