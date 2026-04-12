from __future__ import annotations

from pathlib import Path
from typing import Callable, TYPE_CHECKING

from job_hunter_agent.application.contracts import ApplicationSubmissionResult, ArtifactCapturePort
from job_hunter_agent.collectors.linkedin_application_artifacts import (
    create_linkedin_failure_artifact_capture,
    is_closed_target_error,
    is_page_closed,
)
from job_hunter_agent.collectors.linkedin_application_components import (
    LinkedInApplicationFlowComponents,
    create_linkedin_application_flow_components,
)
from job_hunter_agent.collectors.linkedin_application_entrypoint import (
    canonical_linkedin_job_url,
    classify_linkedin_job_page_readiness,
    extract_linkedin_job_id,
    needs_canonical_job_navigation,
)
from job_hunter_agent.collectors.linkedin_application_entry_strategies import (
    LinkedInApplyClassicModalStrategy,
    LinkedInApplyEntrypointSequence,
    LinkedInApplyHrefEntrypointStrategy,
)
from job_hunter_agent.collectors.linkedin_application_execution import LinkedInEasyApplyExecution
from job_hunter_agent.collectors.linkedin_application_inspection import inspect_linkedin_application
from job_hunter_agent.collectors.linkedin_application_modal import LinkedInEasyApplyModalDriver
from job_hunter_agent.collectors.linkedin_application_opening import LinkedInEasyApplyFlowOpener
from job_hunter_agent.collectors.linkedin_application_runtime import run_linkedin_async
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
from job_hunter_agent.collectors.linkedin_application_submission_flow import submit_linkedin_application
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
        components: LinkedInApplicationFlowComponents | None = None,
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
        self._artifact_capture = artifact_capture or create_linkedin_failure_artifact_capture(
            enabled=self.save_failure_artifacts,
            artifacts_dir=self.failure_artifacts_dir,
        )
        resolved_components = components or create_linkedin_application_flow_components(
            resume_path=self.resume_path,
            contact_email=self.contact_email,
            phone=self.phone,
            phone_country_code=self.phone_country_code,
            candidate_profile=self.candidate_profile,
            candidate_profile_path=self.candidate_profile_path,
            modal_interpreter=self.modal_interpreter,
        )
        self._navigator = resolved_components.navigator
        self._page_reader = resolved_components.page_reader
        self._modal_driver = resolved_components.modal_driver
        self._submitted_at_provider = resolved_components.submitted_at_provider
        self._execution = LinkedInEasyApplyExecution(
            inspect_easy_apply_modal=self._inspect_easy_apply_modal_via_executor,
            try_submit_application=self._try_submit_application,
        )
        self._classic_modal_entrypoint = LinkedInApplyClassicModalStrategy(
            try_open_easy_apply_modal=self._try_open_easy_apply_modal,
            read_page_state=self._read_page_state,
            inspect_open_easy_apply_modal=self._inspect_open_easy_apply_modal,
        )
        self._href_entrypoint = LinkedInApplyHrefEntrypointStrategy(
            extract_easy_apply_href=self._extract_easy_apply_href,
            prepare_job_page_for_apply=self._prepare_job_page_for_apply,
            read_page_state=self._read_page_state,
            inspect_easy_apply_modal=self._inspect_easy_apply_modal_via_opener,
            is_page_closed=self._is_page_closed,
        )
        self._entrypoint_sequence = LinkedInApplyEntrypointSequence(
            (self._classic_modal_entrypoint, self._href_entrypoint)
        )
        self._html_recovery = resolved_components.html_recovery
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
        return self._inspect_sync(job)

    def submit(self, application, job: JobPosting) -> ApplicationSubmissionResult:
        return self._submit_sync(job)

    def _inspect_sync(self, job: JobPosting) -> LinkedInApplicationInspection:
        return run_linkedin_async(self._inspect_async(job))

    def _submit_sync(self, job: JobPosting) -> ApplicationSubmissionResult:
        return run_linkedin_async(self._submit_async(job))

    async def _inspect_async(self, job: JobPosting) -> LinkedInApplicationInspection:
        return await inspect_linkedin_application(
            job=job,
            storage_state_path=self.storage_state_path,
            headless=self.headless,
            ensure_target_job_page=self._ensure_target_job_page,
            read_state_with_hydration=self._read_state_with_hydration,
            capture_failure_artifacts=self._capture_failure_artifacts,
            inspect_preflight_state=self._execution.inspect_preflight_state,
            classify_page_state=classify_linkedin_application_page_state,
            modal_interpretation_formatter=self.modal_interpretation_formatter,
        )

    async def _submit_async(self, job: JobPosting) -> ApplicationSubmissionResult:
        return await submit_linkedin_application(
            job=job,
            storage_state_path=self.storage_state_path,
            headless=self.headless,
            ensure_target_job_page=self._ensure_target_job_page,
            read_state_with_hydration=self._read_state_with_hydration,
            capture_failure_artifacts=self._capture_failure_artifacts,
            prepare_submit_state=self._execution.prepare_submit_state,
            execution_submit=self._execution.submit,
            format_modal_interpretation_for_error=self._format_modal_interpretation_for_error,
            build_submit_exception_result=self._build_submit_exception_result,
            submitted_at_provider=self._submitted_at_provider,
        )

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
        return await self._entrypoint_sequence.open(
            page,
            initial_state=initial_state,
            close_modal=close_modal,
        )

    async def _inspect_open_easy_apply_modal(
        self,
        page,
        initial_state: LinkedInApplicationPageState,
        close_modal: bool,
    ) -> LinkedInApplicationPageState:
        return await self._modal_driver.inspect_open_easy_apply_modal(
            page,
            initial_state,
            read_page_state=self._read_page_state,
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
