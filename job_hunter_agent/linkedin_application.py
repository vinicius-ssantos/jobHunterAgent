from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from job_hunter_agent.browser_support import load_playwright_storage_state, resolve_local_chromium
from job_hunter_agent.domain import JobPosting


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


def classify_linkedin_application_page_state(state: LinkedInApplicationPageState) -> LinkedInApplicationInspection:
    if state.modal_open:
        detail_parts: list[str] = ["preflight real"]
        if state.resumable_fields:
            detail_parts.append(f"campos={', '.join(state.resumable_fields)}")
        if state.modal_submit_visible and not (
            state.modal_next_visible
            or state.modal_review_visible
            or state.modal_file_upload
            or state.modal_questions_visible
        ):
            detail_parts.append("ok: fluxo simplificado aberto no LinkedIn")
            if state.cta_text:
                detail_parts.append(f"cta={state.cta_text}")
            if state.modal_sample:
                detail_parts.append(f"modal={state.modal_sample}")
            return LinkedInApplicationInspection(
                outcome="ready",
                detail=" | ".join(detail_parts),
            )

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
        return LinkedInApplicationInspection(
            outcome="manual_review",
            detail=" | ".join(detail_parts),
        )

    if state.easy_apply:
        return LinkedInApplicationInspection(
            outcome="manual_review",
            detail="preflight real inconclusivo: CTA de candidatura simplificada encontrado, mas modal nao abriu",
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
    def __init__(self, *, storage_state_path: str | Path, headless: bool) -> None:
        self.storage_state_path = Path(storage_state_path).resolve()
        self.headless = headless

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

    def _inspect_sync(self, job: JobPosting) -> LinkedInApplicationInspection:
        import asyncio

        return asyncio.run(self._inspect_async(job))

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
                state = await self._read_page_state(page)
                if state.easy_apply:
                    await self._try_open_easy_apply_modal(page)
                    await page.wait_for_timeout(2500)
                    state = await self._read_page_state(page)
                    await self._try_close_modal(page)
            finally:
                await context.close()
                await browser.close()

        return classify_linkedin_application_page_state(state)

    async def _read_page_state(self, page) -> LinkedInApplicationPageState:
        raw_state = await page.evaluate(
            """
            () => {
              const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
              const texts = Array.from(document.querySelectorAll("button, a"))
                .map((node) => normalize(node.textContent))
                .filter(Boolean);
              const joined = texts.join(" | ");
              const easyApplyTexts = texts.filter((text) => text.includes("easy apply") || text.includes("candidatura simplificada"));
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
                sample: joined.slice(0, 400),
                modal_sample: modalTexts.join(" | ").slice(0, 400),
                contact_email_visible: contactEmailVisible,
                contact_phone_visible: contactPhoneVisible,
                country_code_visible: countryCodeVisible,
                work_authorization_visible: workAuthorizationVisible,
                years_of_experience_visible: yearsOfExperienceVisible,
                resumable_fields: resumableFields,
              };
            }
            """
        )
        raw_state["resumable_fields"] = tuple(raw_state.get("resumable_fields", ()))
        return LinkedInApplicationPageState(**raw_state)

    async def _try_open_easy_apply_modal(self, page) -> None:
        candidates = [
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
                await candidate.click(timeout=3000, force=True)
                if await self._wait_for_modal(page):
                    return
                handle = await candidate.element_handle()
                if handle is not None:
                    await page.evaluate("(element) => element.click()", handle)
                    if await self._wait_for_modal(page):
                        return
            except Exception:
                continue

    async def _wait_for_modal(self, page) -> bool:
        try:
            await page.locator('[role="dialog"]').first.wait_for(state="visible", timeout=3000)
            await page.wait_for_timeout(800)
            return True
        except Exception:
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
