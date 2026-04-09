from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from uuid import uuid4

from job_hunter_agent.core.domain import JobPosting
from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState

ARTIFACT_SCHEMA_VERSION = 1


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
) -> str:
    if not enabled or artifacts_dir is None:
        return ""
    try:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        detail_slug = build_detail_slug(detail)
        artifact_id = f"{phase}-job-{job.id}-{uuid4().hex[:8]}"
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
                html_path.write_text(html, encoding="utf-8")
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
            "captured_at": datetime.now().isoformat(timespec="seconds"),
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
        meta_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        return f" | artefatos={meta_path.name}"
    except Exception:
        return ""
