from __future__ import annotations

from pathlib import Path

from job_hunter_agent.core.candidate_profile import (
    CandidateProfile,
    extract_supported_experience_answers,
    record_pending_questions,
)
from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState


class LinkedInEasyApplyFieldFiller:
    def __init__(
        self,
        *,
        contact_email: str,
        phone: str,
        phone_country_code: str,
        candidate_profile: CandidateProfile | None = None,
        candidate_profile_path: Path | None = None,
    ) -> None:
        self.contact_email = contact_email
        self.phone = phone
        self.phone_country_code = phone_country_code
        self.candidate_profile = candidate_profile
        self.candidate_profile_path = candidate_profile_path

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
              const fillCountryCodeCombo = (field, targetValue, fieldName) => {
                if (!field || field.disabled || !targetValue) return false;
                const targetNormalized = normalize(targetValue);
                const targetDialCode = ((targetValue || '').match(/\\+\\d+/) || [''])[0];
                try {
                  field.focus();
                  field.click();
                } catch {}
                const options = Array.from(
                  modal.querySelectorAll(
                    '[role="option"], [role="listbox"] [aria-label], ul[role="listbox"] li, li[role="option"]'
                  )
                );
                const target = options.find((option) => {
                  const text = normalize(option.textContent || option.getAttribute('aria-label') || '');
                  return (
                    text === targetNormalized
                    || text.includes(targetNormalized)
                    || (!!targetDialCode && text.includes(targetDialCode))
                  );
                });
                if (!target) return false;
                try {
                  target.scrollIntoView({ block: 'nearest' });
                  target.click();
                } catch {
                  return false;
                }
                dispatch(field);
                filled.push(fieldName);
                return true;
              };

              if (email) {
                const field = findField(['email', 'e-mail'], null);
                if (fillSelect(field, email, 'email')) {
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
                const field = findField(
                  [
                    'country code',
                    'codigo do pais',
                    'código do país',
                    'cÃ³digo do paÃ­s',
                    'cÃƒÆ’Ã‚Â³digo do paÃƒÆ’Ã‚Â­s',
                    'country/region phone number',
                  ],
                  null,
                );
                fillSelect(field, countryCode, 'codigo_pais');
                if (!filled.includes('codigo_pais')) {
                  const accentedField = findField(['código do país', 'cÃ³digo do paÃ­s'], null);
                  fillSelect(accentedField, countryCode, 'codigo_pais');
                }
                if (!filled.includes('codigo_pais')) {
                  fillCountryCodeCombo(field, countryCode, 'codigo_pais');
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

    def record_pending_questions(self, questions: tuple[str, ...]) -> None:
        if self.candidate_profile_path is None or not questions:
            return
        try:
            record_pending_questions(self.candidate_profile_path, questions)
        except Exception:
            return
