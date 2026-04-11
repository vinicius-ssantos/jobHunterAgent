from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, TYPE_CHECKING

from job_hunter_agent.application.contracts import ApplicationSubmissionResult, ArtifactCapturePort
from job_hunter_agent.collectors.linkedin_application_artifacts import (
    LinkedInFailureArtifactCapture,
    is_closed_target_error,
    is_page_closed,
)
from job_hunter_agent.collectors.linkedin_application_entrypoint import (
    canonical_linkedin_job_url,
    classify_linkedin_job_page_readiness,
    extract_linkedin_job_id,
    needs_canonical_job_navigation,
    recover_linkedin_direct_apply_url_from_html,
)
from job_hunter_agent.collectors.linkedin_application_entry_strategies import (
    LinkedInApplyHrefEntrypointStrategy,
    LinkedInApplyHtmlRecoveryStrategy,
)
from job_hunter_agent.collectors.linkedin_application_execution import LinkedInEasyApplyExecution
from job_hunter_agent.collectors.linkedin_application_modal import LinkedInEasyApplyModalDriver
from job_hunter_agent.collectors.linkedin_application_navigation import LinkedInEasyApplyNavigator
from job_hunter_agent.collectors.linkedin_application_opening import LinkedInEasyApplyFlowOpener
from job_hunter_agent.collectors.linkedin_application_reader import LinkedInApplicationPageReader
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
from job_hunter_agent.collectors.linkedin_application_submit import (
    evaluate_linkedin_submit_readiness,
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
        artifact_capture: ArtifactCapturePort | None = None,
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
        self._artifact_capture = artifact_capture or LinkedInFailureArtifactCapture(
            enabled=self.save_failure_artifacts,
            artifacts_dir=self.failure_artifacts_dir,
        )
        self._navigator = LinkedInEasyApplyNavigator()
        self._page_reader = LinkedInApplicationPageReader()
        self._modal_driver = LinkedInEasyApplyModalDriver(
            resume_path=self.resume_path,
            contact_email=self.contact_email,
            phone=self.phone,
            phone_country_code=self.phone_country_code,
            candidate_profile=self.candidate_profile,
            candidate_profile_path=self.candidate_profile_path,
            modal_interpreter=self.modal_interpreter,
        )
        self._execution = LinkedInEasyApplyExecution(
            inspect_easy_apply_modal=self._inspect_easy_apply_modal_via_executor,
            try_open_easy_apply_modal=self._try_open_easy_apply_modal,
            try_open_easy_apply_via_direct_url=self._try_open_easy_apply_via_direct_url_via_executor,
            try_submit_application=self._try_submit_application,
            read_page_state=self._read_page_state,
        )
        self._href_entrypoint = LinkedInApplyHrefEntrypointStrategy(
            extract_easy_apply_href=self._extract_easy_apply_href,
            prepare_job_page_for_apply=self._prepare_job_page_for_apply,
            read_page_state=self._read_page_state,
            inspect_easy_apply_modal=self._inspect_easy_apply_modal_via_opener,
            is_page_closed=self._is_page_closed,
        )
        self._html_recovery = LinkedInApplyHtmlRecoveryStrategy()
        self._flow_opener = LinkedInEasyApplyFlowOpener(
            prepare_job_page_for_apply=self._prepare_job_page_for_apply,
            read_page_state=self._read_page_state,
            assess_job_page_readiness=self._assess_job_page_readiness,
            href_entrypoint=self._href_entrypoint,
            html_recovery=self._html_recovery,
        )

    def _refresh_flow_opener_callbacks(self) -> None:
        self._flow_opener._prepare_job_page_for_apply = self._prepare_job_page_for_apply
        self._flow_opener._read_page_state = self._read_page_state
        self._flow_opener._assess_job_page_readiness = self._assess_job_page_readiness
        self._href_entrypoint._extract_easy_apply_href = self._extract_easy_apply_href
        self._href_entrypoint._prepare_job_page_for_apply = self._prepare_job_page_for_apply
        self._href_entrypoint._read_page_state = self._read_page_state
        self._href_entrypoint._inspect_easy_apply_modal = self._inspect_easy_apply_modal_via_opener
        self._href_entrypoint._is_page_closed = self._is_page_closed

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
                state = await self._execution.inspect_preflight_state(page, state)
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
                state = await self._execution.prepare_submit_state(page, state)
                if not state.modal_open or not state.modal_submit_visible:
                    submit_readiness = evaluate_linkedin_submit_readiness(
                        state,
                        interpretation_detail=self._format_modal_interpretation_for_error(state),
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
                        detail=f"{submit_readiness.detail}{artifact_detail}",
                    )
                submitted = await self._execution.submit(page)
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
        return await self._page_reader.read(page)


    def _assess_job_page_readiness(
        self,
        job: JobPosting,
        state: LinkedInApplicationPageState,
    ) -> LinkedInJobPageReadiness:
        return classify_linkedin_job_page_readiness(job_url=job.url, state=state)

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
        return canonical_linkedin_job_url(url)

    @classmethod
    def _needs_canonical_job_navigation(cls, current_url: str, target_url: str) -> bool:
        return needs_canonical_job_navigation(current_url, target_url)

    @staticmethod
    def _extract_linkedin_job_id(url: str) -> str:
        return extract_linkedin_job_id(url)

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

    async def _inspect_easy_apply_modal_via_opener(
        self,
        page,
        initial_state: LinkedInApplicationPageState,
        close_modal: bool,
    ) -> LinkedInApplicationPageState:
        return await self._inspect_easy_apply_modal(
            page,
            initial_state,
            close_modal=close_modal,
        )

    async def _inspect_easy_apply_modal_via_executor(
        self,
        page,
        initial_state: LinkedInApplicationPageState,
        close_modal: bool,
    ) -> LinkedInApplicationPageState:
        return await self._inspect_easy_apply_modal(
            page,
            initial_state,
            close_modal=close_modal,
        )

    async def _capture_failure_artifacts(
        self,
        page,
        *,
        state: LinkedInApplicationPageState,
        job: JobPosting,
        phase: str,
        detail: str,
    ) -> str:
        return await self._artifact_capture.capture(
            page,
            state=state,
            job=job,
            phase=phase,
            detail=detail,
        )

    async def _build_submit_exception_result(
        self,
        exc: Exception,
        *,
        page,
        state: LinkedInApplicationPageState,
        job: JobPosting,
    ) -> ApplicationSubmissionResult:
        return await self._artifact_capture.build_submit_exception_result(
            exc,
            page=page,
            state=state,
            job=job,
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
        self._refresh_flow_opener_callbacks()
        return await self._flow_opener.read_state_with_hydration(page, job)

    async def _recover_easy_apply_from_page_html(self, page, job: JobPosting) -> bool:
        self._refresh_flow_opener_callbacks()
        return await self._flow_opener.recover_easy_apply_from_page_html(page, job)

    async def _try_open_easy_apply_via_direct_url(
        self,
        page,
        *,
        close_modal: bool,
    ) -> LinkedInApplicationPageState:
        self._refresh_flow_opener_callbacks()
        return await self._flow_opener.try_open_easy_apply_via_direct_url(
            page,
            close_modal=close_modal,
        )

    async def _try_open_easy_apply_via_direct_url_via_executor(
        self,
        page,
        close_modal: bool,
    ) -> LinkedInApplicationPageState:
        return await self._try_open_easy_apply_via_direct_url(
            page,
            close_modal=close_modal,
        )

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


