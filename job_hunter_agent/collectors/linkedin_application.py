from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Callable, TYPE_CHECKING

from job_hunter_agent.core.browser_support import load_playwright_storage_state, resolve_local_chromium
from job_hunter_agent.application.applicant import ApplicationSubmissionResult
from job_hunter_agent.collectors.linkedin_application_artifacts import (
    capture_failure_artifacts,
    is_closed_target_error,
    is_page_closed,
)
from job_hunter_agent.collectors.linkedin_application_modal import LinkedInEasyApplyModalDriver
from job_hunter_agent.collectors.linkedin_application_navigation import LinkedInEasyApplyNavigator
from job_hunter_agent.collectors.linkedin_application_state import (
    LinkedInApplicationInspection,
    LinkedInApplicationPageState,
    build_linkedin_modal_snapshot,
    classify_linkedin_application_page_state,
    describe_linkedin_easy_apply_entrypoint,
    describe_linkedin_modal_blocker,
)
from job_hunter_agent.core.domain import JobPosting

if TYPE_CHECKING:
    from job_hunter_agent.collectors.linkedin_modal_llm import LinkedInModalInterpretation


class LinkedInApplicationFlowInspector:
    def __init__(
        self,
        *,
        storage_state_path: str | Path,
        headless: bool,
        resume_path: str | Path | None = None,
        contact_email: str = "",
        phone: str = "",
        phone_country_code: str = "",
        modal_interpretation_formatter: Callable[[LinkedInApplicationPageState], str] | None = None,
        modal_interpreter: Callable[[LinkedInApplicationPageState], "LinkedInModalInterpretation"] | None = None,
        save_failure_artifacts: bool = False,
        failure_artifacts_dir: str | Path | None = None,
    ) -> None:
        self.storage_state_path = Path(storage_state_path).resolve()
        self.headless = headless
        self.resume_path = Path(resume_path).resolve() if resume_path else None
        self.contact_email = contact_email.strip()
        self.phone = phone.strip()
        self.phone_country_code = phone_country_code.strip()
        self.modal_interpretation_formatter = modal_interpretation_formatter
        self.modal_interpreter = modal_interpreter
        self.save_failure_artifacts = save_failure_artifacts
        self.failure_artifacts_dir = Path(failure_artifacts_dir).resolve() if failure_artifacts_dir else None
        self._navigator = LinkedInEasyApplyNavigator()
        self._modal_driver = LinkedInEasyApplyModalDriver(
            resume_path=self.resume_path,
            contact_email=self.contact_email,
            phone=self.phone,
            phone_country_code=self.phone_country_code,
            modal_interpreter=self.modal_interpreter,
        )

    def inspect(self, job: JobPosting) -> LinkedInApplicationInspection:
        if "linkedin.com/jobs/" not in job.url.lower():
            return LinkedInApplicationInspection(
                outcome="ignored",
                detail="vaga nao pertence ao fluxo interno do LinkedIn",
            )
        if not self.storage_state_path.exists():
            return LinkedInApplicationInspection(
                outcome="error",
                detail="sessao autenticada do LinkedIn nao encontrada para inspecao real",
            )
        return self._inspect_sync(job)

    def submit(self, application, job: JobPosting) -> ApplicationSubmissionResult:
        if "linkedin.com/jobs/" not in job.url.lower():
            return ApplicationSubmissionResult(
                status="error_submit",
                detail="submissao real indisponivel para vaga fora do LinkedIn interno",
            )
        if not self.storage_state_path.exists():
            return ApplicationSubmissionResult(
                status="error_submit",
                detail="sessao autenticada do LinkedIn nao encontrada para submissao real",
            )
        return self._submit_sync(job)

    def _inspect_sync(self, job: JobPosting) -> LinkedInApplicationInspection:
        import asyncio

        return asyncio.run(self._inspect_async(job))

    def _submit_sync(self, job: JobPosting) -> ApplicationSubmissionResult:
        import asyncio

        return asyncio.run(self._submit_async(job))

    async def _inspect_async(self, job: JobPosting) -> LinkedInApplicationInspection:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Dependencias de candidatura assistida nao estao instaladas. Rode pip install -r requirements.txt."
            ) from exc

        executable_path = resolve_local_chromium()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                executable_path=str(executable_path),
                headless=self.headless,
                args=["--start-maximized"],
            )
            context = await browser.new_context(storage_state=load_playwright_storage_state(self.storage_state_path))
            page = await context.new_page()
            try:
                await page.goto(job.url, wait_until="domcontentloaded")
                await page.wait_for_timeout(2500)
                await self._prepare_job_page_for_apply(page)
                state = await self._read_page_state(page)
                if state.easy_apply:
                    state = await self._inspect_easy_apply_modal(page, state)
                    if state.easy_apply and not state.modal_open:
                        artifact_detail = await self._capture_failure_artifacts(
                            page,
                            state=state,
                            job=job,
                            phase="preflight",
                            detail="preflight real inconclusivo: CTA de candidatura simplificada encontrado, mas modal nao abriu",
                        )
                    else:
                        artifact_detail = ""
                else:
                    artifact_detail = ""
            finally:
                await context.close()
                await browser.close()

        inspection = classify_linkedin_application_page_state(state)
        if self.modal_interpretation_formatter is not None and state.modal_open:
            try:
                extra = self.modal_interpretation_formatter(state).strip()
            except Exception:
                extra = ""
            if extra:
                inspection = LinkedInApplicationInspection(
                    outcome=inspection.outcome,
                    detail=f"{inspection.detail} | {extra}",
                )
        if artifact_detail:
            inspection = LinkedInApplicationInspection(
                outcome=inspection.outcome,
                detail=f"{inspection.detail}{artifact_detail}",
            )
        return inspection

    async def _submit_async(self, job: JobPosting) -> ApplicationSubmissionResult:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Dependencias de candidatura assistida nao estao instaladas. Rode pip install -r requirements.txt."
            ) from exc

        executable_path = resolve_local_chromium()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                executable_path=str(executable_path),
                headless=self.headless,
                args=["--start-maximized"],
            )
            context = await browser.new_context(storage_state=load_playwright_storage_state(self.storage_state_path))
            page = await context.new_page()
            state = LinkedInApplicationPageState()
            try:
                await page.goto(job.url, wait_until="domcontentloaded")
                await page.wait_for_timeout(2500)
                await self._prepare_job_page_for_apply(page)
                state = await self._read_page_state(page)
                if not state.easy_apply:
                    return ApplicationSubmissionResult(
                        status="error_submit",
                        detail="submissao real bloqueada: CTA de candidatura simplificada nao encontrado",
                    )
                state = await self._inspect_easy_apply_modal(page, state, close_modal=False)
                if not state.modal_open:
                    await self._try_open_easy_apply_modal(page)
                    await page.wait_for_timeout(1800)
                    state = await self._read_page_state(page)
                    if state.modal_open:
                        state = await self._inspect_easy_apply_modal(page, state, close_modal=False)
                if not state.modal_open or not state.modal_submit_visible:
                    interpretation_detail = self._format_modal_interpretation_for_error(state)
                    artifact_detail = await self._capture_failure_artifacts(
                        page,
                        state=state,
                        job=job,
                        phase="submit",
                        detail=(
                            "submissao real bloqueada: fluxo nao chegou ao botao de envio"
                            f" | bloqueio={describe_linkedin_modal_blocker(state)}"
                        ),
                    )
                    return ApplicationSubmissionResult(
                        status="error_submit",
                        detail=(
                            "submissao real bloqueada: fluxo nao chegou ao botao de envio"
                            f" | bloqueio={describe_linkedin_modal_blocker(state)}"
                            f" | modal={state.modal_sample or 'nao_informado'}"
                            f" | {describe_linkedin_easy_apply_entrypoint(state)}"
                            f"{interpretation_detail}"
                            f"{artifact_detail}"
                        ),
                    )
                submitted = await self._try_submit_application(page)
                if not submitted:
                    artifact_detail = await self._capture_failure_artifacts(
                        page,
                        state=state,
                        job=job,
                        phase="submit",
                        detail="submissao real falhou: clique final de envio nao confirmou sucesso",
                    )
                    return ApplicationSubmissionResult(
                        status="error_submit",
                        detail=(
                            "submissao real falhou: clique final de envio nao confirmou sucesso"
                            f"{artifact_detail}"
                        ),
                    )
                return ApplicationSubmissionResult(
                    status="submitted",
                    detail="submissao real concluida no LinkedIn",
                    submitted_at=datetime.now().isoformat(timespec="seconds"),
                )
            except Exception as exc:
                return await self._build_submit_exception_result(exc, page=page, state=state, job=job)
            finally:
                await context.close()
                await browser.close()

    async def _read_page_state(self, page) -> LinkedInApplicationPageState:
        raw_state = await page.evaluate(
            """
            () => {
              const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
              const currentUrl = window.location.href || "";
              const main = document.querySelector('main') || document.body;
              const detailPanel =
                document.querySelector('.jobs-search__job-details--container') ||
                document.querySelector('.jobs-details') ||
                main;
              const topCard =
                detailPanel.querySelector('.jobs-details-top-card') ||
                detailPanel.querySelector('[data-live-test-job-apply-button]') ||
                detailPanel;
              const prioritizedSelectors = [
                '[data-live-test-job-apply-button]',
                '[data-control-name="jobdetails_topcard_inapply"]',
                '[data-control-name="topcard_inapply"]',
                '[data-control-name="jobs-details-top-card-apply-button"]',
                '.jobs-apply-button',
                '.jobs-apply-button--top-card button',
                '.jobs-s-apply button',
              ];
              const prioritizedNodes = prioritizedSelectors.flatMap((selector) =>
                Array.from(topCard.querySelectorAll(selector))
              );
              const prioritizedTexts = prioritizedNodes
                .map((node) => normalize(node.textContent || node.getAttribute('aria-label') || ''))
                .filter(Boolean);
              const texts = Array.from(detailPanel.querySelectorAll("button, a"))
                .map((node) => normalize(node.textContent || node.getAttribute('aria-label') || ''))
                .filter(Boolean);
              const joined = normalize(detailPanel.innerText || "").slice(0, 400);
              const easyApplyTexts = (prioritizedTexts.length ? prioritizedTexts : texts)
                .filter((text) => text.includes("easy apply") || text.includes("candidatura simplificada"));
              const applyFlowActive = currentUrl.includes("/apply/") || currentUrl.includes("openSDUIApplyFlow=true");
              const externalApply = texts.some((text) => text.includes("candidate-se") || text.includes("apply on company website"));
              const submitVisible = texts.some((text) => text.includes("enviar candidatura") || text.includes("submit application"));

              const confirmationDialog = document.querySelector('[role="alertdialog"]');
              const confirmationTexts = confirmationDialog
                ? Array.from(confirmationDialog.querySelectorAll("button, span, div, h1, h2, h3, p"))
                    .map((node) => normalize(node.textContent))
                    .filter(Boolean)
                : [];
              const confirmationJoined = confirmationTexts.join(" | ");
              const saveApplicationDialogVisible = confirmationJoined.includes("salvar esta candidatura")
                || confirmationJoined.includes("save this application");

              const modal = document.querySelector('[role="dialog"]');
              const modalButtonTexts = modal
                ? Array.from(modal.querySelectorAll("button"))
                    .map((node) => normalize(node.textContent))
                    .filter(Boolean)
                : [];
              const modalTexts = modal
                ? Array.from(modal.querySelectorAll("button, label, span, div, h2, h3, p, legend"))
                    .map((node) => normalize(node.textContent))
                    .filter(Boolean)
                : [];
              const modalInputNames = modal
                ? Array.from(modal.querySelectorAll("input, textarea, select"))
                    .map((node) => normalize(node.getAttribute("name") || node.getAttribute("aria-label") || node.id || ""))
                    .filter(Boolean)
                : [];
              const modalHeadings = modal
                ? Array.from(modal.querySelectorAll("h1, h2, h3, legend"))
                    .map((node) => normalize(node.textContent))
                    .filter(Boolean)
                : [];
              const hasText = (items, parts) => parts.some((part) => items.some((value) => value.includes(part)));
              const resumableFields = [];
              const contactEmailVisible = hasText(modalTexts, ["email"]) || hasText(modalInputNames, ["email"]);
              const contactPhoneVisible = hasText(modalTexts, ["phone", "telefone", "celular"]) || hasText(modalInputNames, ["phone", "telefone", "celular"]);
              const countryCodeVisible = hasText(modalTexts, ["country code", "codigo do pais", "código do país"]) || hasText(modalInputNames, ["country code", "codigo", "código"]);
              const workAuthorizationVisible = hasText(modalTexts, ["work authorization", "work permit", "autoriz", "visa"]) || hasText(modalInputNames, ["authorization", "permit", "visa"]);
              const yearsOfExperienceVisible = hasText(modalTexts, ["years of work experience", "anos de experiencia", "anos de experiência"]) || hasText(modalInputNames, ["years", "experience", "experiência"]);
              if (contactEmailVisible) resumableFields.push("email");
              if (contactPhoneVisible) resumableFields.push("telefone");
              if (countryCodeVisible) resumableFields.push("codigo_pais");
              if (workAuthorizationVisible) resumableFields.push("autorizacao_trabalho");
              if (yearsOfExperienceVisible) resumableFields.push("anos_experiencia");
              return {
                easy_apply: easyApplyTexts.length > 0 || applyFlowActive,
                external_apply: externalApply,
                submit_visible: submitVisible,
                modal_open: !!modal,
                modal_submit_visible: modalButtonTexts.some((text) => text.includes("submit application") || text.includes("enviar candidatura")),
                modal_next_visible: modalButtonTexts.some((text) => text.includes("next") || text.includes("continuar") || text.includes("avancar") || text.includes("avançar")),
                modal_review_visible: modalButtonTexts.some((text) => text.includes("review") || text.includes("revisar")),
                modal_file_upload: modal ? modal.querySelectorAll('input[type="file"]').length > 0 : false,
                modal_questions_visible: modalTexts.some((text) => text.includes("required") || text.includes("obrigat") || text.includes("question")),
                save_application_dialog_visible: saveApplicationDialogVisible,
                cta_text: easyApplyTexts[0] || "",
                sample: `${currentUrl} | ${joined}`.slice(0, 400),
                modal_sample: (modalTexts.join(" | ") || confirmationJoined).slice(0, 400),
                contact_email_visible: contactEmailVisible,
                contact_phone_visible: contactPhoneVisible,
                country_code_visible: countryCodeVisible,
                work_authorization_visible: workAuthorizationVisible,
                years_of_experience_visible: yearsOfExperienceVisible,
                resumable_fields: resumableFields,
                filled_fields: [],
                progressed_to_next_step: false,
                uploaded_resume: false,
                reached_review_step: false,
                ready_to_submit: false,
                modal_headings: modalHeadings.slice(0, 6),
                modal_buttons: modalButtonTexts.slice(0, 8),
                modal_fields: modalInputNames.slice(0, 8),
              };
            }
            """
        )
        raw_state["resumable_fields"] = tuple(raw_state.get("resumable_fields", ()))
        raw_state["filled_fields"] = tuple(raw_state.get("filled_fields", ()))
        raw_state["modal_headings"] = tuple(raw_state.get("modal_headings", ()))
        raw_state["modal_buttons"] = tuple(raw_state.get("modal_buttons", ()))
        raw_state["modal_fields"] = tuple(raw_state.get("modal_fields", ()))
        return LinkedInApplicationPageState(**raw_state)

    async def _inspect_easy_apply_modal(
        self,
        page,
        initial_state: LinkedInApplicationPageState,
        *,
        close_modal: bool = True,
    ) -> LinkedInApplicationPageState:
        return await self._modal_driver.inspect_easy_apply_modal(
            page,
            initial_state=initial_state,
            read_page_state=self._read_page_state,
            try_open_easy_apply_modal=self._try_open_easy_apply_modal,
            close_modal=close_modal,
        )

    def _interpret_modal_state(self, state: LinkedInApplicationPageState):
        return self._modal_driver.interpret_modal_state(state)

    def _format_modal_interpretation_for_error(self, state: LinkedInApplicationPageState) -> str:
        return self._modal_driver.format_modal_interpretation_for_error(state)

    async def _capture_failure_artifacts(self, page, *, state: LinkedInApplicationPageState, job: JobPosting, phase: str, detail: str) -> str:
        return await capture_failure_artifacts(
            page,
            state=state,
            job=job,
            phase=phase,
            detail=detail,
            enabled=self.save_failure_artifacts,
            artifacts_dir=self.failure_artifacts_dir,
        )

    async def _build_submit_exception_result(
        self,
        exc: Exception,
        *,
        page,
        state: LinkedInApplicationPageState,
        job: JobPosting,
    ) -> ApplicationSubmissionResult:
        if self._is_closed_target_error(exc):
            detail = "submissao real interrompida: pagina do LinkedIn foi fechada durante a automacao"
        else:
            detail = f"submissao real falhou com erro inesperado: {exc}"
        artifact_detail = await self._capture_failure_artifacts(
            page,
            state=state,
            job=job,
            phase="submit",
            detail=detail,
        )
        return ApplicationSubmissionResult(
            status="error_submit",
            detail=f"{detail}{artifact_detail}",
        )

    async def _try_open_easy_apply_modal(self, page) -> bool:
        return await self._navigator.try_open_easy_apply_modal(page)

    async def _extract_easy_apply_href(self, page) -> str:
        return await self._navigator.extract_easy_apply_href(page)

    async def _wait_for_apply_flow(self, page) -> bool:
        return await self._navigator.wait_for_apply_flow(page)

    async def _wait_for_modal(self, page) -> bool:
        return await self._navigator.wait_for_modal(page)

    async def _prepare_job_page_for_apply(self, page) -> None:
        await self._navigator.prepare_job_page_for_apply(page)

    async def _dismiss_interfering_dialogs(self, page) -> None:
        if await self._handle_save_application_dialog(page):
            return
        candidates = [
            page.get_by_role("button", name=re.compile(r"(dismiss|close|fechar|cancel|cancelar|not now|agora nao|agora não|skip)", re.IGNORECASE)).first,
            page.locator('[role="dialog"] button[aria-label*="Dismiss"], [role="dialog"] button[aria-label*="Close"], [role="dialog"] button[aria-label*="Fechar"]').first,
            page.locator('button[aria-label*="Dismiss"], button[aria-label*="Close"], button[aria-label*="Fechar"]').first,
        ]
        for candidate in candidates:
            try:
                if await candidate.count() == 0:
                    continue
                await candidate.click(timeout=1500)
                await page.wait_for_timeout(500)
            except Exception:
                continue

    async def _handle_save_application_dialog(self, page) -> bool:
        if self._is_page_closed(page):
            return False
        candidates = [
            page.locator('[role="alertdialog"] [data-control-name="discard_application_confirm_btn"]').first,
            page.locator('[role="alertdialog"] button').filter(has_text=re.compile(r"(discard|descartar)", re.IGNORECASE)).first,
            page.get_by_role("button", name=re.compile(r"^(discard|descartar)$", re.IGNORECASE)).first,
        ]
        for candidate in candidates:
            try:
                if await candidate.count() == 0:
                    continue
                await candidate.click(timeout=2000, force=True)
                await page.wait_for_timeout(900)
                return True
            except Exception:
                continue
        return False

    @staticmethod
    def _is_page_closed(page) -> bool:
        return is_page_closed(page)

    @staticmethod
    def _is_closed_target_error(exc: Exception) -> bool:
        return is_closed_target_error(exc)

    async def _try_fill_safe_fields(self, page) -> tuple[str, ...]:
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

              if (email) {
                const field = findField(['email'], null);
                if (field && !field.disabled && !field.readOnly) {
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
                const field = findField(['country code', 'codigo do pais', 'código do país', 'country/region phone number'], 'select');
                if (field && !field.disabled) {
                  const options = Array.from(field.options || []);
                  const target = options.find((option) => {
                    const label = normalize(option.label || option.textContent || '');
                    const value = normalize(option.value || '');
                    return label.includes(normalize(countryCode)) || value.includes(normalize(countryCode));
                  });
                  if (target) {
                    field.value = target.value;
                    dispatch(field);
                    filled.push('codigo_pais');
                  }
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

    async def _try_advance_single_step(self, page) -> bool:
        candidates = [
            page.get_by_role(
                "button",
                name=re.compile(r"(next|continuar|avancar|avançar)", re.IGNORECASE),
            ).first,
            page.locator('[role="dialog"] button').filter(
                has_text=re.compile(r"(next|continuar|avancar|avançar)", re.IGNORECASE)
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

    async def _try_upload_resume(self, page) -> bool:
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

    async def _try_open_review_step(self, page) -> bool:
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

    async def _try_close_modal(self, page) -> None:
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

    async def _try_submit_application(self, page) -> bool:
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
                if await self._detect_submit_success(page):
                    return True
            except Exception:
                continue
        return False

    async def _detect_submit_success(self, page) -> bool:
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
