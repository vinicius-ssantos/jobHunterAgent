from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Callable, TYPE_CHECKING

from job_hunter_agent.browser_support import load_playwright_storage_state, resolve_local_chromium
from job_hunter_agent.applicant import ApplicationSubmissionResult
from job_hunter_agent.domain import JobPosting

if TYPE_CHECKING:
    from job_hunter_agent.linkedin_modal_llm import LinkedInModalInterpretation


@dataclass(frozen=True)
class LinkedInApplicationInspection:
    outcome: str
    detail: str


@dataclass(frozen=True)
class LinkedInApplicationPageState:
    easy_apply: bool = False
    external_apply: bool = False
    submit_visible: bool = False
    modal_open: bool = False
    modal_submit_visible: bool = False
    modal_next_visible: bool = False
    modal_review_visible: bool = False
    modal_file_upload: bool = False
    modal_questions_visible: bool = False
    cta_text: str = ""
    sample: str = ""
    modal_sample: str = ""
    contact_email_visible: bool = False
    contact_phone_visible: bool = False
    country_code_visible: bool = False
    work_authorization_visible: bool = False
    years_of_experience_visible: bool = False
    resumable_fields: tuple[str, ...] = ()
    filled_fields: tuple[str, ...] = ()
    progressed_to_next_step: bool = False
    uploaded_resume: bool = False
    reached_review_step: bool = False
    ready_to_submit: bool = False
    modal_headings: tuple[str, ...] = ()
    modal_buttons: tuple[str, ...] = ()
    modal_fields: tuple[str, ...] = ()


def build_linkedin_modal_snapshot(state: LinkedInApplicationPageState) -> str:
    parts: list[str] = []
    if state.modal_headings:
        parts.append(f"titulos={', '.join(state.modal_headings[:3])}")
    if state.modal_buttons:
        parts.append(f"botoes={', '.join(state.modal_buttons[:5])}")
    if state.modal_fields:
        parts.append(f"campos_detectados={', '.join(state.modal_fields[:5])}")
    if not parts:
        return "snapshot_modal=indisponivel"
    return "snapshot_modal=" + " | ".join(parts)


def describe_linkedin_modal_blocker(state: LinkedInApplicationPageState) -> str:
    blockers: list[str] = []
    if not state.modal_open:
        blockers.append("modal_fechado")
    if state.modal_questions_visible:
        blockers.append("perguntas_obrigatorias")
    if state.modal_file_upload and not state.uploaded_resume:
        blockers.append("upload_cv_pendente")
    if state.modal_next_visible and not state.progressed_to_next_step:
        blockers.append("etapa_intermediaria")
    if state.modal_review_visible and not state.reached_review_step:
        blockers.append("revisao_nao_alcancada")
    if not state.modal_submit_visible:
        blockers.append("botao_submit_ausente")
    if state.resumable_fields and not state.filled_fields:
        blockers.append("campos_nao_preenchidos")
    if not blockers:
        blockers.append("estado_modal_inconclusivo")
    return ", ".join(blockers)


def describe_linkedin_easy_apply_entrypoint(state: LinkedInApplicationPageState) -> str:
    parts: list[str] = []
    if state.cta_text:
        parts.append(f"cta={state.cta_text}")
    if state.sample:
        parts.append(f"pagina={state.sample[:180]}")
    if not parts:
        return "entrada_easy_apply=indisponivel"
    return " | ".join(parts)


def classify_linkedin_application_page_state(state: LinkedInApplicationPageState) -> LinkedInApplicationInspection:
    if state.modal_open:
        detail_parts: list[str] = ["preflight real"]
        if state.resumable_fields:
            detail_parts.append(f"campos={', '.join(state.resumable_fields)}")
        if state.filled_fields:
            detail_parts.append(f"preenchidos={', '.join(state.filled_fields)}")
        if state.progressed_to_next_step:
            detail_parts.append("avancou_proxima_etapa=sim")
        if state.uploaded_resume:
            detail_parts.append("curriculo_carregado=sim")
        if state.reached_review_step:
            detail_parts.append("revisao_final_alcancada=sim")
        if state.ready_to_submit:
            detail_parts.append("pronto_para_envio=sim")
        if state.ready_to_submit or (
            state.modal_submit_visible and not (
                state.modal_next_visible
                or state.modal_review_visible
                or state.modal_file_upload
                or state.modal_questions_visible
            )
        ):
            detail_parts.append("ok: fluxo pronto para submissao assistida no LinkedIn")
            if state.cta_text:
                detail_parts.append(f"cta={state.cta_text}")
            if state.modal_sample:
                detail_parts.append(f"modal={state.modal_sample}")
            detail_parts.append(build_linkedin_modal_snapshot(state))
            return LinkedInApplicationInspection(
                outcome="ready",
                detail=" | ".join(detail_parts),
            )

        if state.modal_submit_visible and not (
            state.modal_next_visible
            or state.modal_review_visible
            or state.modal_file_upload
            or state.modal_questions_visible
        ):
            detail_parts.append("ok: fluxo simplificado aberto no LinkedIn")

        detail_parts.append("inconclusivo: fluxo do LinkedIn exige revisao manual")
        if state.modal_next_visible:
            detail_parts.append("passos_adicionais=sim")
        if state.modal_review_visible:
            detail_parts.append("revisao_final=sim")
        if state.modal_file_upload:
            detail_parts.append("upload_cv=sim")
        if state.modal_questions_visible:
            detail_parts.append("perguntas=sim")
        if state.cta_text:
            detail_parts.append(f"cta={state.cta_text}")
        if state.modal_sample:
            detail_parts.append(f"modal={state.modal_sample}")
        detail_parts.append(build_linkedin_modal_snapshot(state))
        return LinkedInApplicationInspection(
            outcome="manual_review",
            detail=" | ".join(detail_parts),
        )

    if state.easy_apply:
        return LinkedInApplicationInspection(
            outcome="manual_review",
            detail=(
                "preflight real inconclusivo: CTA de candidatura simplificada encontrado, mas modal nao abriu"
                f" | {describe_linkedin_easy_apply_entrypoint(state)}"
            ),
        )
    if state.external_apply:
        return LinkedInApplicationInspection(
            outcome="blocked",
            detail="preflight real bloqueado: vaga redireciona para candidatura externa",
        )
    if state.submit_visible:
        return LinkedInApplicationInspection(
            outcome="manual_review",
            detail="preflight real inconclusivo: pagina interna com CTA de envio sem fluxo simples claro",
        )
    return LinkedInApplicationInspection(
        outcome="blocked",
        detail="preflight real bloqueado: CTA de candidatura nao encontrado na pagina do LinkedIn",
    )


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
    ) -> None:
        self.storage_state_path = Path(storage_state_path).resolve()
        self.headless = headless
        self.resume_path = Path(resume_path).resolve() if resume_path else None
        self.contact_email = contact_email.strip()
        self.phone = phone.strip()
        self.phone_country_code = phone_country_code.strip()
        self.modal_interpretation_formatter = modal_interpretation_formatter
        self.modal_interpreter = modal_interpreter

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
                    return ApplicationSubmissionResult(
                        status="error_submit",
                        detail=(
                            "submissao real bloqueada: fluxo nao chegou ao botao de envio"
                            f" | bloqueio={describe_linkedin_modal_blocker(state)}"
                            f" | modal={state.modal_sample or 'nao_informado'}"
                            f" | {describe_linkedin_easy_apply_entrypoint(state)}"
                            f"{interpretation_detail}"
                        ),
                    )
                submitted = await self._try_submit_application(page)
                if not submitted:
                    return ApplicationSubmissionResult(
                        status="error_submit",
                        detail="submissao real falhou: clique final de envio nao confirmou sucesso",
                    )
                return ApplicationSubmissionResult(
                    status="submitted",
                    detail="submissao real concluida no LinkedIn",
                    submitted_at=datetime.now().isoformat(timespec="seconds"),
                )
            finally:
                await context.close()
                await browser.close()

    async def _read_page_state(self, page) -> LinkedInApplicationPageState:
        raw_state = await page.evaluate(
            """
            () => {
              const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
              const main = document.querySelector('main') || document.body;
              const topCard = document.querySelector('.jobs-details-top-card') || main;
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
              const texts = Array.from(main.querySelectorAll("button, a"))
                .map((node) => normalize(node.textContent))
                .filter(Boolean);
              const joined = normalize(main.innerText || "").slice(0, 400);
              const easyApplyTexts = (prioritizedTexts.length ? prioritizedTexts : texts)
                .filter((text) => text.includes("easy apply") || text.includes("candidatura simplificada"));
              const externalApply = texts.some((text) => text.includes("candidate-se") || text.includes("apply on company website"));
              const submitVisible = texts.some((text) => text.includes("enviar candidatura") || text.includes("submit application"));

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
                easy_apply: easyApplyTexts.length > 0,
                external_apply: externalApply,
                submit_visible: submitVisible,
                modal_open: !!modal,
                modal_submit_visible: modalButtonTexts.some((text) => text.includes("submit application") || text.includes("enviar candidatura")),
                modal_next_visible: modalButtonTexts.some((text) => text.includes("next") || text.includes("continuar") || text.includes("avancar") || text.includes("avançar")),
                modal_review_visible: modalButtonTexts.some((text) => text.includes("review") || text.includes("revisar")),
                modal_file_upload: modal ? modal.querySelectorAll('input[type="file"]').length > 0 : false,
                modal_questions_visible: modalTexts.some((text) => text.includes("required") || text.includes("obrigat") || text.includes("question")),
                cta_text: easyApplyTexts[0] || "",
                sample: joined,
                modal_sample: modalTexts.join(" | ").slice(0, 400),
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
        state = initial_state
        opened = False
        for _ in range(2):
            await self._try_open_easy_apply_modal(page)
            await page.wait_for_timeout(2500)
            state = await self._read_page_state(page)
            if state.modal_open:
                opened = True
                break
        if not opened:
            return state

        all_filled_fields: tuple[str, ...] = ()
        progressed = False
        uploaded_resume = False
        reached_review_step = False
        ready_to_submit = False

        for _ in range(5):
            filled_fields = await self._try_fill_safe_fields(page)
            if filled_fields:
                all_filled_fields = tuple(dict.fromkeys((*all_filled_fields, *filled_fields)))
                await page.wait_for_timeout(1200)
            state = await self._read_page_state(page)
            if all_filled_fields:
                state = LinkedInApplicationPageState(
                    **{
                        **state.__dict__,
                        "filled_fields": tuple(dict.fromkeys((*state.filled_fields, *all_filled_fields))),
                    }
                )

            if state.modal_open and state.modal_submit_visible and not state.modal_next_visible:
                ready_to_submit = True
                break

            moved = False
            interpretation = self._interpret_modal_state(state)
            action = interpretation.recommended_action
            if action == "submit_if_authorized" and state.modal_open and state.modal_submit_visible and not state.modal_next_visible:
                ready_to_submit = True
                break
            if action == "upload_resume" and state.modal_open and state.modal_file_upload and not uploaded_resume:
                uploaded_resume = await self._try_upload_resume(page)
                if uploaded_resume:
                    moved = True
                    await page.wait_for_timeout(1800)
                    state = await self._read_page_state(page)
            elif action == "open_review" and state.modal_open and state.modal_review_visible and not state.modal_submit_visible:
                review_opened = await self._try_open_review_step(page)
                if review_opened:
                    reached_review_step = True
                    moved = True
                    await page.wait_for_timeout(1800)
                    state = await self._read_page_state(page)
            elif action == "click_next" and state.modal_open and state.modal_next_visible and not state.modal_submit_visible:
                next_progressed = await self._try_advance_single_step(page)
                if next_progressed:
                    progressed = True
                    moved = True
                    await page.wait_for_timeout(2200)
                    state = await self._read_page_state(page)
            elif state.modal_open and state.modal_file_upload and not uploaded_resume:
                uploaded_resume = await self._try_upload_resume(page)
                if uploaded_resume:
                    moved = True
                    await page.wait_for_timeout(1800)
                    state = await self._read_page_state(page)
            elif state.modal_open and state.modal_review_visible and not state.modal_submit_visible:
                review_opened = await self._try_open_review_step(page)
                if review_opened:
                    reached_review_step = True
                    moved = True
                    await page.wait_for_timeout(1800)
                    state = await self._read_page_state(page)
            elif state.modal_open and state.modal_next_visible and not state.modal_submit_visible:
                next_progressed = await self._try_advance_single_step(page)
                if next_progressed:
                    progressed = True
                    moved = True
                    await page.wait_for_timeout(2200)
                    state = await self._read_page_state(page)

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
            await self._try_close_modal(page)
        return state

    def _interpret_modal_state(self, state: LinkedInApplicationPageState):
        if self.modal_interpreter is None:
            from job_hunter_agent.linkedin_modal_llm import deterministic_interpret_linkedin_modal

            return deterministic_interpret_linkedin_modal(state)
        try:
            return self.modal_interpreter(state)
        except Exception:
            from job_hunter_agent.linkedin_modal_llm import deterministic_interpret_linkedin_modal

            return deterministic_interpret_linkedin_modal(state)

    def _format_modal_interpretation_for_error(self, state: LinkedInApplicationPageState) -> str:
        if not state.modal_open:
            return ""
        try:
            from job_hunter_agent.linkedin_modal_llm import format_linkedin_modal_interpretation

            interpretation = self._interpret_modal_state(state)
            return f" | {format_linkedin_modal_interpretation(interpretation)}"
        except Exception:
            return ""

    async def _try_open_easy_apply_modal(self, page) -> bool:
        await self._dismiss_interfering_dialogs(page)
        candidates = [
            page.locator('[data-live-test-job-apply-button] button, button[data-live-test-job-apply-button]').first,
            page.locator('[data-control-name="jobdetails_topcard_inapply"]').first,
            page.locator('[data-control-name="topcard_inapply"]').first,
            page.locator('[data-control-name="jobs-details-top-card-apply-button"]').first,
            page.locator('.jobs-apply-button--top-card button').first,
            page.locator('.jobs-s-apply button').first,
            page.locator('button.jobs-apply-button').first,
            page.locator('button[aria-label*="Easy Apply" i]').first,
            page.locator('button[aria-label*="Candidatura simplificada" i]').first,
            page.get_by_role(
                "button",
                name=re.compile(r"(easy apply|candidatura simplificada)", re.IGNORECASE),
            ).first,
            page.locator("button, a").filter(has_text=re.compile(r"(easy apply|candidatura simplificada)", re.IGNORECASE)).first,
        ]
        for candidate in candidates:
            try:
                if await candidate.count() == 0:
                    continue
                await candidate.scroll_into_view_if_needed()
                await page.wait_for_timeout(400)
                try:
                    await candidate.hover(timeout=1500)
                except Exception:
                    pass
                await candidate.click(timeout=3500)
                if await self._wait_for_modal(page):
                    return True
                await candidate.click(timeout=3500, force=True)
                if await self._wait_for_modal(page):
                    return True
                handle = await candidate.element_handle()
                if handle is not None:
                    await page.evaluate("(element) => element.click()", handle)
                    if await self._wait_for_modal(page):
                        return True
            except Exception:
                continue
        fallback_opened = await page.evaluate(
            """
            () => {
              const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
              const candidates = Array.from(document.querySelectorAll('button, a'));
              for (const element of candidates) {
                const text = normalize(element.textContent);
                const aria = normalize(element.getAttribute('aria-label') || '');
                const control = normalize(element.getAttribute('data-control-name') || '');
                const matchesText = text.includes('easy apply') || text.includes('candidatura simplificada');
                const matchesAria = aria.includes('easy apply') || aria.includes('candidatura simplificada');
                const matchesControl = control.includes('inapply') || control.includes('apply-button');
                if (!(matchesText || matchesAria || matchesControl)) continue;
                element.click();
                return true;
              }
              return false;
            }
            """
        )
        if fallback_opened and await self._wait_for_modal(page):
            return True
        await self._dismiss_interfering_dialogs(page)
        return False

    async def _wait_for_modal(self, page) -> bool:
        try:
            await page.locator('[role="dialog"]').first.wait_for(state="visible", timeout=4500)
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(1400)
            return True
        except Exception:
            return False

    async def _prepare_job_page_for_apply(self, page) -> None:
        try:
            await page.locator("main").first.wait_for(state="visible", timeout=5000)
        except Exception:
            return
        await page.wait_for_timeout(1200)
        await self._dismiss_interfering_dialogs(page)
        await page.evaluate(
            """
            () => {
              const target =
                document.querySelector('.jobs-details-top-card') ||
                document.querySelector('[data-live-test-job-apply-button]') ||
                document.querySelector('.jobs-search__job-details--container') ||
                document.querySelector('main');
              if (target) {
                target.scrollIntoView({ behavior: 'instant', block: 'center' });
              }
            }
            """
        )
        await page.wait_for_timeout(600)

    async def _dismiss_interfering_dialogs(self, page) -> None:
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
