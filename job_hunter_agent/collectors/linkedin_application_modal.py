from __future__ import annotations

from pathlib import Path
import re
from typing import Callable

from job_hunter_agent.core.candidate_profile import (
    CandidateProfile,
    extract_supported_experience_answers,
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
        modal_interpreter: Callable[[LinkedInApplicationPageState], object] | None = None,
    ) -> None:
        self.resume_path = resume_path
        self.contact_email = contact_email
        self.phone = phone
        self.phone_country_code = phone_country_code
        self.candidate_profile = candidate_profile
        self.modal_interpreter = modal_interpreter

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

            if state.modal_open and state.modal_submit_visible and not state.modal_next_visible:
                ready_to_submit = True
                break

            moved = False
            interpretation = self.interpret_modal_state(state)
            action = interpretation.recommended_action
            if action == "submit_if_authorized" and state.modal_open and state.modal_submit_visible and not state.modal_next_visible:
                ready_to_submit = True
                break
            if action == "upload_resume" and state.modal_open and state.modal_file_upload and not uploaded_resume:
                uploaded_resume = await self.try_upload_resume(page)
                if uploaded_resume:
                    moved = True
                    await page.wait_for_timeout(1800)
                    state = await read_page_state(page)
            elif action == "open_review" and state.modal_open and state.modal_review_visible and not state.modal_submit_visible:
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
            elif state.modal_open and state.modal_review_visible and not state.modal_submit_visible:
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

            if state.modal_open and state.modal_submit_visible and not state.modal_next_visible:
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
        if await page.locator('[role="dialog"]').count() == 0:
            return ()
        filled = await page.evaluate(
            """
            ({ email, phone, countryCode }) => {
              const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
              const modal = document.querySelector('[role="dialog"]');
              if (!modal) return [];

              const fields = Array.from(modal.querySelectorAll('input, textarea, select'));
              const descriptorFor = (node) => {
                const parts = [];
                const labelId = node.getAttribute('aria-labelledby');
                if (labelId) {
                  labelId.split(/\\s+/).forEach((id) => {
                    const labelNode = document.getElementById(id);
                    if (labelNode) parts.push(labelNode.textContent || '');
                  });
                }
                const closestLabel = node.closest('label');
                if (closestLabel) parts.push(closestLabel.textContent || '');
                const parentText = node.parentElement ? node.parentElement.textContent || '' : '';
                parts.push(parentText);
                parts.push(node.getAttribute('aria-label') || '');
                parts.push(node.getAttribute('name') || '');
                parts.push(node.id || '');
                return normalize(parts.join(' '));
              };
              const findField = (patterns, tagName) => {
                return fields.find((field) => {
                  if (tagName && field.tagName.toLowerCase() !== tagName) return false;
                  const descriptor = descriptorFor(field);
                  return patterns.some((pattern) => descriptor.includes(pattern));
                });
              };
              const filled = [];
              const dispatch = (node) => {
                node.dispatchEvent(new Event('input', { bubbles: true }));
                node.dispatchEvent(new Event('change', { bubbles: true }));
                node.dispatchEvent(new Event('blur', { bubbles: true }));
              };
              const fillSelect = (field, targetValue, fieldName) => {
                if (!field || field.tagName.toLowerCase() !== 'select' || field.disabled || !targetValue) return false;
                const targetNormalized = normalize(targetValue);
                const targetDialCode = ((targetValue || '').match(/\\+\\d+/) || [''])[0];
                const options = Array.from(field.options || []);
                const target = options.find((option) => {
                  const label = normalize(option.label || option.textContent || '');
                  const value = normalize(option.value || '');
                  return (
                    label === targetNormalized
                    || value === targetNormalized
                    || label.includes(targetNormalized)
                    || value.includes(targetNormalized)
                    || (!!targetDialCode && (label.includes(targetDialCode) || value.includes(targetDialCode)))
                  );
                });
                if (!target) return false;
                field.value = target.value;
                dispatch(field);
                filled.push(fieldName);
                return true;
              };

              if (email) {
                const field = findField(['email', 'e-mail'], null);
                if (fillSelect(field, email, 'email')) {
                  // select preenchido
                } else if (field && !field.disabled && !field.readOnly) {
                  field.focus();
                  field.value = email;
                  dispatch(field);
                  filled.push('email');
                }
              }

              if (phone) {
                const field = findField(['phone', 'telefone', 'celular'], null);
                if (field && !field.disabled && !field.readOnly) {
                  field.focus();
                  field.value = phone;
                  dispatch(field);
                  filled.push('telefone');
                }
              }

              if (countryCode) {
                const field = findField(['country code', 'codigo do pais', 'código do país', 'cÃƒÂ³digo do paÃƒÂ­s', 'country/region phone number'], 'select');
                fillSelect(field, countryCode, 'codigo_pais');
                if (!filled.includes('codigo_pais')) {
                  const accentedField = findField(['código do país'], 'select');
                  fillSelect(accentedField, countryCode, 'codigo_pais');
                }
              }

              return filled;
            }
            """,
            {
                "email": self.contact_email,
                "phone": self.phone,
                "countryCode": self.phone_country_code,
            },
        )
        return tuple(filled)

    async def try_fill_supported_profile_answers(
        self,
        page,
        state: LinkedInApplicationPageState,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        answers, unresolved_questions = extract_supported_experience_answers(
            state.modal_questions,
            self.candidate_profile,
        )
        if not answers:
            return (), unresolved_questions
        answered_questions = await page.evaluate(
            """
            (answers) => {
              const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
              const modal = document.querySelector('[role="dialog"]');
              if (!modal) return [];
              const fields = Array.from(modal.querySelectorAll('input[required], textarea[required], select[required]'));
              const descriptorFor = (field) => {
                const parts = [];
                const fieldId = field.getAttribute('id');
                if (fieldId) {
                  const explicitLabel = modal.querySelector(`label[for="${fieldId}"]`);
                  if (explicitLabel) parts.push(explicitLabel.textContent || '');
                }
                const labelledBy = field.getAttribute('aria-labelledby');
                if (labelledBy) {
                  labelledBy.split(/\\s+/).forEach((id) => {
                    const node = document.getElementById(id);
                    if (node) parts.push(node.textContent || '');
                  });
                }
                const describedBy = field.getAttribute('aria-describedby');
                if (describedBy) {
                  describedBy.split(/\\s+/).forEach((id) => {
                    const node = document.getElementById(id);
                    if (node) parts.push(node.textContent || '');
                  });
                }
                const closestLabel = field.closest('label');
                if (closestLabel) parts.push(closestLabel.textContent || '');
                const formElement = field.closest('[data-test-form-element]') || field.closest('.fb-dash-form-element');
                if (formElement) {
                  const legend = formElement.querySelector('legend');
                  const title = formElement.querySelector('[data-test-text-entity-list-form-title]');
                  if (legend) parts.push(legend.textContent || '');
                  if (title) parts.push(title.textContent || '');
                }
                parts.push(field.getAttribute('name') || '');
                parts.push(field.getAttribute('aria-label') || '');
                return normalize(parts.join(' '));
              };
              const dispatch = (node) => {
                node.dispatchEvent(new Event('input', { bubbles: true }));
                node.dispatchEvent(new Event('change', { bubbles: true }));
                node.dispatchEvent(new Event('blur', { bubbles: true }));
              };
              const filled = [];
              for (const answer of answers) {
                const normalizedQuestion = normalize(answer.question || '');
                const aliases = (answer.aliases || []).map((alias) => normalize(alias));
                const field = fields.find((candidate) => {
                  const descriptor = descriptorFor(candidate);
                  return (
                    (!!normalizedQuestion && descriptor.includes(normalizedQuestion))
                    || aliases.some((alias) => alias && descriptor.includes(alias))
                  );
                });
                if (!field || field.disabled || field.readOnly) {
                  continue;
                }
                const tagName = field.tagName.toLowerCase();
                if (tagName === 'select') {
                  const targetValue = String(answer.years);
                  const target = Array.from(field.options || []).find((option) => {
                    const label = normalize(option.label || option.textContent || '');
                    const value = normalize(option.value || '');
                    return label === targetValue || value === targetValue;
                  });
                  if (!target) {
                    continue;
                  }
                  field.value = target.value;
                  dispatch(field);
                  filled.push(answer.question);
                  continue;
                }
                if (tagName === 'input' || tagName === 'textarea') {
                  field.focus();
                  field.value = String(answer.years);
                  dispatch(field);
                  filled.push(answer.question);
                }
              }
              return filled;
            }
            """,
            [
                {
                    "question": answer.question,
                    "years": answer.years,
                    "aliases": list(answer.aliases),
                }
                for answer in answers
            ],
        )
        answered_questions = tuple(answered_questions)
        unanswered_remaining = tuple(
            question for question in unresolved_questions if question not in answered_questions
        )
        unanswered_from_answers = tuple(
            answer.question for answer in answers if answer.question not in answered_questions
        )
        unresolved = tuple(dict.fromkeys((*unanswered_remaining, *unanswered_from_answers)))
        return answered_questions, unresolved

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


