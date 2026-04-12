from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
import re
from uuid import uuid4

from job_hunter_agent.application.contracts import (
    ApplicationSubmissionResult,
    ArtifactClockPort,
    ArtifactFilesystemPort,
    ArtifactIdGeneratorPort,
)
from job_hunter_agent.collectors.linkedin_application_diagnostics import (
    build_submit_closed_page_detail,
    build_submit_unexpected_failure_detail,
    extract_operational_detail_category,
)
from job_hunter_agent.core.domain import JobPosting
from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState

ARTIFACT_SCHEMA_VERSION = 1


class SystemArtifactClock:
    def filename_timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    def event_timestamp(self) -> str:
        return datetime.now().isoformat(timespec="seconds")


class LocalArtifactFilesystem:
    def ensure_directory(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None:
        path.write_text(content, encoding=encoding)

    def write_json(self, path: Path, payload: object, *, encoding: str = "utf-8") -> None:
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding=encoding)


class UuidArtifactIdGenerator:
    def next_short_id(self) -> str:
        return uuid4().hex[:8]


@dataclass(frozen=True)
class LinkedInFailureArtifactCapture:
    enabled: bool
    artifacts_dir: Path | None
    clock: ArtifactClockPort = field(default_factory=SystemArtifactClock)
    filesystem: ArtifactFilesystemPort = field(default_factory=LocalArtifactFilesystem)
    artifact_id_generator: ArtifactIdGeneratorPort = field(default_factory=UuidArtifactIdGenerator)

    async def capture(
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
            enabled=self.enabled,
            artifacts_dir=self.artifacts_dir,
            clock=self.clock,
            filesystem=self.filesystem,
            artifact_id_generator=self.artifact_id_generator,
        )

    async def build_submit_exception_result(
        self,
        exc: Exception,
        *,
        page,
        state: LinkedInApplicationPageState,
        job: JobPosting,
    ) -> ApplicationSubmissionResult:
        if is_closed_target_error(exc):
            detail = build_submit_closed_page_detail()
        else:
            detail = build_submit_unexpected_failure_detail(exc)
        artifact_detail = await self.capture(
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


def create_linkedin_failure_artifact_capture(
    *,
    enabled: bool,
    artifacts_dir: Path | None,
    clock: ArtifactClockPort | None = None,
    filesystem: ArtifactFilesystemPort | None = None,
    artifact_id_generator: ArtifactIdGeneratorPort | None = None,
) -> LinkedInFailureArtifactCapture:
    return LinkedInFailureArtifactCapture(
        enabled=enabled,
        artifacts_dir=artifacts_dir,
        clock=clock or SystemArtifactClock(),
        filesystem=filesystem or LocalArtifactFilesystem(),
        artifact_id_generator=artifact_id_generator or UuidArtifactIdGenerator(),
    )


def is_page_closed(page) -> bool:
    try:
        return bool(page.is_closed())
    except Exception:
        return True


def is_closed_target_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "target page, context or browser has been closed" in text


def build_detail_slug(detail: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", detail.lower()).strip("-")
    if not normalized:
        return "sem-detalhe"
    return normalized[:64].rstrip("-")


async def capture_failure_artifacts(
    page,
    *,
    state: LinkedInApplicationPageState,
    job: JobPosting,
    phase: str,
    detail: str,
    enabled: bool,
    artifacts_dir: Path | None,
    clock: ArtifactClockPort,
    filesystem: ArtifactFilesystemPort,
    artifact_id_generator: ArtifactIdGeneratorPort,
) -> str:
    if not enabled or artifacts_dir is None:
        return ""
    try:
        filesystem.ensure_directory(artifacts_dir)
        timestamp = clock.filename_timestamp()
        detail_slug = build_detail_slug(detail)
        artifact_id = f"{phase}-job-{job.id}-{artifact_id_generator.next_short_id()}"
        stem = f"{timestamp}_{phase}_job-{job.id}_{detail_slug}"
        html_path = artifacts_dir / f"{stem}_dom.html"
        screenshot_path = artifacts_dir / f"{stem}_screenshot.png"
        meta_path = artifacts_dir / f"{stem}_meta.json"
        page_closed = is_page_closed(page)
        html_saved = False
        screenshot_saved = False

        if not page_closed:
            try:
                html = await page.content()
                filesystem.write_text(html_path, html)
                html_saved = True
            except Exception as exc:
                if is_closed_target_error(exc):
                    page_closed = True
        try:
            if not page_closed:
                await page.screenshot(path=str(screenshot_path), full_page=True)
                screenshot_saved = True
        except Exception as exc:
            if is_closed_target_error(exc):
                page_closed = True

        payload = {
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "artifact_id": artifact_id,
            "artifact_type": phase,
            "detail_slug": detail_slug,
            "job_id": job.id,
            "job_title": job.title,
            "job_url": job.url,
            "phase": phase,
            "detail": detail,
            "detail_category": extract_operational_detail_category(detail),
            "captured_at": clock.event_timestamp(),
            "state": {
                "easy_apply": state.easy_apply,
                "modal_open": state.modal_open,
                "modal_submit_visible": state.modal_submit_visible,
                "modal_next_visible": state.modal_next_visible,
                "modal_review_visible": state.modal_review_visible,
                "modal_file_upload": state.modal_file_upload,
                "modal_questions_visible": state.modal_questions_visible,
                "save_application_dialog_visible": state.save_application_dialog_visible,
                "cta_text": state.cta_text,
                "sample": state.sample,
                "modal_sample": state.modal_sample,
                "modal_headings": list(state.modal_headings),
                "modal_buttons": list(state.modal_buttons),
                "modal_fields": list(state.modal_fields),
                "modal_questions": list(state.modal_questions),
                "answered_questions": list(state.answered_questions),
                "unanswered_questions": list(state.unanswered_questions),
                "resumable_fields": list(state.resumable_fields),
                "filled_fields": list(state.filled_fields),
            },
            "page_closed": page_closed,
            "files": {
                "html": str(html_path) if html_saved else "",
                "screenshot": str(screenshot_path) if screenshot_saved else "",
            },
        }
        filesystem.write_json(meta_path, payload)
        return f" | artefatos={meta_path.name}"
    except Exception:
        return ""
