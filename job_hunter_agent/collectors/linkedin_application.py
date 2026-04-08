from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Callable, TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

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
    LinkedInJobPageReadiness,
    build_linkedin_modal_snapshot,
    classify_linkedin_application_page_state,
    describe_linkedin_easy_apply_entrypoint,
    describe_linkedin_job_page_readiness,
    describe_linkedin_modal_blocker,
)
from job_hunter_agent.core.browser_support import load_playwright_storage_state, resolve_local_chromium
from job_hunter_agent.core.candidate_profile import CandidateProfile
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
        candidate_profile: CandidateProfile | None = None,
        candidate_profile_path: str | Path | None = None,
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
        self.candidate_profile = candidate_profile
        self.candidate_profile_path = Path(candidate_profile_path).resolve() if candidate_profile_path else None
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
            candidate_profile=self.candidate_profile,
            candidate_profile_path=self.candidate_profile_path,
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
                await self._ensure_target_job_page(page, job)
                state, readiness = await self._read_state_with_hydration(page, job)
                if readiness.result != "ready":
                    artifact_detail = await self._capture_failure_artifacts(
                        page,
                        state=state,
                        job=job,
                        phase="preflight",
                        detail=f"preflight real bloqueado: {describe_linkedin_job_page_readiness(readiness)}",
                    )
                    inspection = LinkedInApplicationInspection(
                        outcome="blocked",
                        detail=f"preflight real bloqueado: {describe_linkedin_job_page_readiness(readiness)}{artifact_detail}",
                    )
                    return inspection
                if state.easy_apply:
                    state = await self._inspect_easy_apply_modal(page, state)
                    if state.easy_apply and not state.modal_open:
                        state = await self._try_open_easy_apply_via_direct_url(page, close_modal=True)
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
                await self._ensure_target_job_page(page, job)
                state, readiness = await self._read_state_with_hydration(page, job)
                if readiness.result != "ready":
                    artifact_detail = await self._capture_failure_artifacts(
                        page,
                        state=state,
                        job=job,
                        phase="submit",
                        detail=f"submissao real bloqueada: {describe_linkedin_job_page_readiness(readiness)}",
                    )
                    return ApplicationSubmissionResult(
                        status="error_submit",
                        detail=f"submissao real bloqueada: {describe_linkedin_job_page_readiness(readiness)}{artifact_detail}",
                    )
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
                if not state.modal_open and state.easy_apply:
                    state = await self._try_open_easy_apply_via_direct_url(page, close_modal=False)
                if not state.modal_open or not state.modal_submit_visible:
                    interpretation_detail = self._format_modal_interpretation_for_error(state)
                    snapshot_detail = (
                        f" | {build_linkedin_modal_snapshot(state)}"
                        if state.modal_open
                        else ""
                    )
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
                            f"{snapshot_detail}"
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
              const isExcludedNode = (node) => !!node?.closest(
                '[componentkey^="JobDetailsSimilarJobsSlot_"], [data-sdui-component*="similarJobs"]'
              );
              const currentUrl = window.location.href || "";
              const currentPath = `${window.location.origin || ''}${window.location.pathname || ''}`;
              const hiddenPayload = Array.from(document.querySelectorAll('code, script[type="application/ld+json"]'))
                .map((node) => normalize(node.textContent || ''))
                .join(' | ')
                .slice(0, 4000);
              const main = document.querySelector('main') || document.body;
              const detailCandidates = [
                '.jobs-search__job-details--container .jobs-details-top-card',
                '.jobs-details-top-card',
                '.jobs-search__job-details--container',
                '.jobs-details',
                'div[role="main"][data-sdui-screen*="JobDetails"]',
                '#workspace',
                'main',
              ];
              const detailPanel =
                detailCandidates
                  .map((selector) => document.querySelector(selector))
                  .find((node) => !!node)
                || main;
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
                Array.from(topCard.querySelectorAll(selector)).filter((node) => !isExcludedNode(node))
              );
              const globalApplyNodes = Array.from(main.querySelectorAll("button, a"))
                .filter((node) => !isExcludedNode(node))
                .filter((node) => {
                  if (node.closest('header, footer, nav')) return false;
                  const href = (node.getAttribute('href') || '').toLowerCase();
                  const text = normalize(node.textContent || node.getAttribute('aria-label') || '');
                  const control = normalize(node.getAttribute('data-control-name') || '');
                  return (
                    text.includes("easy apply")
                    || text.includes("candidatura simplificada")
                    || href.includes("/apply/")
                    || control.includes("inapply")
                    || control.includes("apply-button")
                  );
                });
              const prioritizedTexts = prioritizedNodes
                .map((node) => normalize(node.textContent || node.getAttribute('aria-label') || ''))
                .filter(Boolean);
              const globalApplyTexts = globalApplyNodes
                .map((node) => normalize(node.textContent || node.getAttribute('aria-label') || ''))
                .filter(Boolean);
              const texts = Array.from(detailPanel.querySelectorAll("button, a"))
                .filter((node) => !isExcludedNode(node))
                .map((node) => normalize(node.textContent || node.getAttribute('aria-label') || ''))
                .filter(Boolean);
              const applyContext = globalApplyNodes[0]?.closest('section, article, div');
              const joined = normalize(
                applyContext?.innerText
                || detailPanel.innerText
                || topCard.innerText
                || main.innerText
                || ""
              ).slice(0, 400);
              const easyApplyTexts = (prioritizedTexts.length ? prioritizedTexts : (globalApplyTexts.length ? globalApplyTexts : texts))
                .filter((text) => text.includes("easy apply") || text.includes("candidatura simplificada"));
              const applyHrefVisible = globalApplyNodes.some((node) =>
                ((node.getAttribute('href') || '').toLowerCase().includes('/apply/'))
              );
              const applyFlowActive = currentUrl.includes("/apply/") || currentUrl.includes("openSDUIApplyFlow=true");
              const hiddenEasyApply = hiddenPayload.includes('onsiteapply')
                || hiddenPayload.includes('applyctatext')
                || hiddenPayload.includes('candidatura simplificada');
              const externalApply = texts.some((text) =>
                text.includes("candidate-se")
                || text.includes("candidatar-se")
                || text.includes("apply on company website")
                || text.includes("site da empresa")
              );
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
              const fieldDescriptor = (field) => {
                if (!field) return "";
                const parts = [];
                const fieldId = field.getAttribute("id");
                if (fieldId) {
                  const explicitLabel = modal.querySelector(`label[for="${fieldId}"]`);
                  if (explicitLabel) parts.push(explicitLabel.textContent || "");
                }
                const labelledBy = field.getAttribute("aria-labelledby");
                if (labelledBy) {
                  labelledBy.split(/\\s+/).forEach((id) => {
                    const labelNode = document.getElementById(id);
                    if (labelNode) parts.push(labelNode.textContent || "");
                  });
                }
                const describedBy = field.getAttribute("aria-describedby");
                if (describedBy) {
                  describedBy.split(/\\s+/).forEach((id) => {
                    const describedNode = document.getElementById(id);
                    if (describedNode) parts.push(describedNode.textContent || "");
                  });
                }
                const closestLabel = field.closest("label");
                if (closestLabel) parts.push(closestLabel.textContent || "");
                const formElement = field.closest("[data-test-form-element]") || field.closest(".fb-dash-form-element");
                if (formElement) {
                  const legend = formElement.querySelector("legend");
                  const title = formElement.querySelector("[data-test-text-entity-list-form-title]");
                  if (legend) parts.push(legend.textContent || "");
                  if (title) parts.push(title.textContent || "");
                }
                parts.push(field.getAttribute("name") || "");
                parts.push(field.getAttribute("aria-label") || "");
                return normalize(parts.join(" "));
              };
              const hasText = (items, parts) => parts.some((part) => items.some((value) => value.includes(part)));
              const resumableFields = [];
              const contactEmailVisible = hasText(modalTexts, ["email", "e-mail"]) || hasText(modalInputNames, ["email"]);
              const contactPhoneVisible = hasText(modalTexts, ["phone", "telefone", "celular"]) || hasText(modalInputNames, ["phone", "telefone", "celular"]);
              const countryCodeVisible = hasText(modalTexts, ["country code", "codigo do pais", "código do país"]) || hasText(modalInputNames, ["country code", "codigo", "código"]);
              const workAuthorizationVisible = hasText(modalTexts, ["work authorization", "work permit", "autoriz", "visa"]) || hasText(modalInputNames, ["authorization", "permit", "visa"]);
              const yearsOfExperienceVisible = hasText(modalTexts, ["years of work experience", "anos de experiencia"]) || hasText(modalInputNames, ["years", "experience"]);
              if (contactEmailVisible) resumableFields.push("email");
              if (contactPhoneVisible) resumableFields.push("telefone");
              if (countryCodeVisible) resumableFields.push("codigo_pais");
              if (workAuthorizationVisible) resumableFields.push("autorizacao_trabalho");
              if (yearsOfExperienceVisible) resumableFields.push("anos_experiencia");
              const requiredFields = modal
                ? Array.from(modal.querySelectorAll('input[required], textarea[required], select[required]'))
                    .map((field) => fieldDescriptor(field))
                    .filter(Boolean)
                : [];
              const modalQuestions = requiredFields.filter((descriptor) => !(
                descriptor.includes("email")
                || descriptor.includes("e-mail")
                || descriptor.includes("phone")
                || descriptor.includes("telefone")
                || descriptor.includes("celular")
                || descriptor.includes("country code")
                || descriptor.includes("codigo do pais")
                || descriptor.includes("código do país")
                || descriptor.includes("cÃ³digo do paÃ­s")
                || descriptor.includes("resume")
                || descriptor.includes("curriculo")
              ));
                return {
                current_url: currentUrl,
                easy_apply: easyApplyTexts.length > 0 || applyHrefVisible || applyFlowActive || hiddenEasyApply,
                external_apply: externalApply,
                submit_visible: submitVisible,
                modal_open: !!modal,
                modal_submit_visible: modalButtonTexts.some((text) => text.includes("submit application") || text.includes("enviar candidatura")),
                modal_next_visible: modalButtonTexts.some((text) => text.includes("next") || text.includes("continuar") || text.includes("avancar") || text.includes("avançar")),
                modal_review_visible: modalButtonTexts.some((text) => text.includes("review") || text.includes("revisar")),
                modal_file_upload: modal ? modal.querySelectorAll('input[type="file"]').length > 0 : false,
                modal_questions_visible: modalQuestions.length > 0,
                save_application_dialog_visible: saveApplicationDialogVisible,
                cta_text: easyApplyTexts[0] || (hiddenEasyApply ? "candidatura simplificada" : ""),
                sample: `${currentPath} | ${joined}`.slice(0, 400),
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
                modal_questions: modalQuestions.slice(0, 6),
              };
            }
            """
        )
        raw_state["resumable_fields"] = tuple(raw_state.get("resumable_fields", ()))
        raw_state["filled_fields"] = tuple(raw_state.get("filled_fields", ()))
        raw_state["modal_headings"] = tuple(raw_state.get("modal_headings", ()))
        raw_state["modal_buttons"] = tuple(raw_state.get("modal_buttons", ()))
        raw_state["modal_fields"] = tuple(raw_state.get("modal_fields", ()))
        raw_state["modal_questions"] = tuple(raw_state.get("modal_questions", ()))
        return LinkedInApplicationPageState(**raw_state)

    def _assess_job_page_readiness(
        self,
        job: JobPosting,
        state: LinkedInApplicationPageState,
    ) -> LinkedInJobPageReadiness:
        current_url = state.current_url or ""
        current_job_id = self._extract_linkedin_job_id(current_url)
        target_job_id = self._extract_linkedin_job_id(job.url)
        normalized_url = current_url.lower()
        normalized_sample = state.sample.lower()

        expired_patterns = (
            r"job (is )?no longer available",
            r"job.*no longer open",
            r"this job has expired",
            r"job posting has expired",
            r"this (position|role|job) (is )?no longer",
            r"this job (listing )?is closed",
            r"job (listing )?not found",
            r"pagina que voce esta procurando nao existe",
            r"vaga (nao|não) esta mais disponivel",
            r"vaga encerrada",
            r"n(a|ã|Ã£)o aceita mais candidaturas",
            r"não aceita mais candidaturas",
            r"no longer accepting applications",
        )

        if "/jobs/collections/" in normalized_url or "/jobs/search/" in normalized_url:
            return LinkedInJobPageReadiness(
                result="listing_redirect",
                reason="a navegacao caiu em listagem ou colecao do LinkedIn",
                sample=state.sample,
            )
        if current_job_id and target_job_id and current_job_id != target_job_id:
            return LinkedInJobPageReadiness(
                result="wrong_page",
                reason="a pagina aberta nao corresponde a vaga autorizada",
                sample=state.sample,
            )
        if any(re.search(pattern, normalized_sample, re.IGNORECASE) for pattern in expired_patterns):
            return LinkedInJobPageReadiness(
                result="expired",
                reason="a vaga parece encerrada ou indisponivel",
                sample=state.sample,
            )
        if state.easy_apply or state.submit_visible:
            return LinkedInJobPageReadiness(
                result="ready",
                reason="cta de candidatura detectado na pagina alvo",
                sample=state.sample,
            )
        if state.external_apply:
            return LinkedInJobPageReadiness(
                result="no_apply_cta",
                reason="a vaga so oferece candidatura externa no site da empresa",
                sample=state.sample,
            )
        if "/apply/" in normalized_url:
            return LinkedInJobPageReadiness(
                result="ready",
                reason="fluxo de candidatura do LinkedIn ja esta aberto na vaga alvo",
                sample=state.sample,
            )
        return LinkedInJobPageReadiness(
            result="no_apply_cta",
            reason="nenhum cta de candidatura foi encontrado na pagina alvo",
            sample=state.sample,
        )

    async def _ensure_target_job_page(self, page, job: JobPosting) -> None:
        current_url = ""
        try:
            current_url = page.url or ""
        except Exception:
            return
        canonical_url = self._canonical_linkedin_job_url(job.url)
        if not canonical_url:
            return
        if not self._needs_canonical_job_navigation(current_url, job.url):
            return
        try:
            await page.goto(canonical_url, wait_until="domcontentloaded")
        except Exception:
            return

    @staticmethod
    def _canonical_linkedin_job_url(url: str) -> str:
        match = re.search(r"/jobs/view/(\d+)", url, re.IGNORECASE)
        if not match:
            return ""
        return f"https://www.linkedin.com/jobs/view/{match.group(1)}/"

    @classmethod
    def _needs_canonical_job_navigation(cls, current_url: str, target_url: str) -> bool:
        target_job_id = cls._extract_linkedin_job_id(target_url)
        if not target_job_id:
            return False
        normalized_current_url = current_url.lower()
        if "/jobs/collections/" in normalized_current_url:
            return True
        if "/apply/" in normalized_current_url:
            return False
        current_job_id = cls._extract_linkedin_job_id(current_url)
        if current_job_id and current_job_id != target_job_id:
            return True
        return False

    @staticmethod
    def _extract_linkedin_job_id(url: str) -> str:
        match = re.search(r"/jobs/view/(\d+)", url, re.IGNORECASE)
        if match:
            return match.group(1)
        try:
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
        except Exception:
            return ""
        current_job_id = query.get("currentJobId", [""])
        if current_job_id and current_job_id[0].isdigit():
            return current_job_id[0]
        reference_job_id = query.get("referenceJobId", [""])
        if reference_job_id and reference_job_id[0].isdigit():
            return reference_job_id[0]
        return ""

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

    async def _capture_failure_artifacts(
        self,
        page,
        *,
        state: LinkedInApplicationPageState,
        job: JobPosting,
        phase: str,
        detail: str,
    ) -> str:
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
        await self._navigator.dismiss_interfering_dialogs(page)

    async def _handle_save_application_dialog(self, page) -> bool:
        return await self._navigator.handle_save_application_dialog(page)

    async def _read_state_with_hydration(
        self,
        page,
        job: JobPosting,
    ) -> tuple[LinkedInApplicationPageState, LinkedInJobPageReadiness]:
        await page.wait_for_timeout(2500)
        await self._prepare_job_page_for_apply(page)
        state = await self._read_page_state(page)
        readiness = self._assess_job_page_readiness(job, state)
        if readiness.result != "no_apply_cta":
            return state, readiness
        for delay_ms in (1800, 2800):
            try:
                await page.wait_for_load_state("domcontentloaded")
            except Exception:
                pass
            await page.wait_for_timeout(delay_ms)
            await self._prepare_job_page_for_apply(page)
            state = await self._read_page_state(page)
            readiness = self._assess_job_page_readiness(job, state)
            if readiness.result != "no_apply_cta":
                return state, readiness
        recovered = await self._recover_easy_apply_from_page_html(page, job)
        if recovered:
            await self._prepare_job_page_for_apply(page)
            state = await self._read_page_state(page)
            readiness = self._assess_job_page_readiness(job, state)
        return state, readiness

    async def _recover_easy_apply_from_page_html(self, page, job: JobPosting) -> bool:
        try:
            content = await page.content()
        except Exception:
            return False
        if not content:
            return False
        lowered = content.lower()
        target_job_id = self._extract_linkedin_job_id(job.url)
        if not target_job_id:
            return False
        has_internal_apply = (
            f"https://www.linkedin.com/job-apply/{target_job_id}".lower() in lowered
            or f"/jobs/view/{target_job_id}/apply/".lower() in lowered
            or (
                "applyctatext" in lowered
                and ("candidatura simplificada" in lowered or "easy apply" in lowered)
            )
        )
        if not has_internal_apply:
            return False
        apply_url = f"https://www.linkedin.com/jobs/view/{target_job_id}/apply/?openSDUIApplyFlow=true"
        try:
            await page.goto(apply_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1800)
            return True
        except Exception:
            return False

    async def _try_open_easy_apply_via_direct_url(
        self,
        page,
        *,
        close_modal: bool,
    ) -> LinkedInApplicationPageState:
        direct_apply_url = await self._extract_easy_apply_href(page)
        if not direct_apply_url:
            return await self._read_page_state(page)
        try:
            await page.goto(direct_apply_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1800)
            await self._prepare_job_page_for_apply(page)
            state = await self._read_page_state(page)
            if state.modal_open:
                return await self._inspect_easy_apply_modal(page, state, close_modal=close_modal)
            return state
        except Exception:
            if self._is_page_closed(page):
                raise
            return await self._read_page_state(page)

    @staticmethod
    def _is_page_closed(page) -> bool:
        return is_page_closed(page)

    @staticmethod
    def _is_closed_target_error(exc: Exception) -> bool:
        return is_closed_target_error(exc)

    async def _try_fill_safe_fields(self, page) -> tuple[str, ...]:
        return await self._modal_driver.try_fill_safe_fields(page)

    async def _try_advance_single_step(self, page) -> bool:
        return await self._modal_driver.try_advance_single_step(page)

    async def _try_upload_resume(self, page) -> bool:
        return await self._modal_driver.try_upload_resume(page)

    async def _try_open_review_step(self, page) -> bool:
        return await self._modal_driver.try_open_review_step(page)

    async def _try_close_modal(self, page) -> None:
        await self._modal_driver.try_close_modal(page)

    async def _try_submit_application(self, page) -> bool:
        return await self._modal_driver.try_submit_application(page)

    async def _detect_submit_success(self, page) -> bool:
        return await self._modal_driver.detect_submit_success(page)
