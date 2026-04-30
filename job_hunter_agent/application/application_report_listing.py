from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from job_hunter_agent.application.application_report import DEFAULT_APPLICATION_REPORTS_DIR


@dataclass(frozen=True)
class ApplicationReportListItem:
    report_path: Path
    manifest_path: Path | None
    application_id: int | None
    job_id: int | None
    application_status: str | None
    job_status: str | None
    company: str | None
    title: str | None
    generated_at_utc: str | None
    manifest_status: str
    modified_at: float


def list_application_reports(
    *,
    reports_dir: Path = DEFAULT_APPLICATION_REPORTS_DIR,
    limit: int = 20,
) -> list[ApplicationReportListItem]:
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    if not reports_dir.exists():
        return []
    items = [_build_item_from_markdown(path) for path in reports_dir.glob("*.md") if path.is_file()]
    items.sort(key=lambda item: item.modified_at, reverse=True)
    return items[:limit]


def render_application_reports_list(
    *,
    reports_dir: Path = DEFAULT_APPLICATION_REPORTS_DIR,
    limit: int = 20,
) -> str:
    items = list_application_reports(reports_dir=reports_dir, limit=limit)
    if not items:
        return f"Nenhum relatorio encontrado em {reports_dir}"
    lines = [f"Relatorios A-F em {reports_dir}:"]
    for item in items:
        lines.extend(
            [
                f"- application_id={_value(item.application_id)} job_id={_value(item.job_id)} "
                f"status={_value(item.application_status)} job_status={_value(item.job_status)}",
                f"  empresa={_value(item.company)} titulo={_value(item.title)}",
                f"  gerado_em={_value(item.generated_at_utc)} manifesto={item.manifest_status}",
                f"  markdown={item.report_path}",
                f"  json={_value(item.manifest_path)}",
            ]
        )
    return "\n".join(lines)


def _build_item_from_markdown(report_path: Path) -> ApplicationReportListItem:
    manifest_path = report_path.with_suffix(".json")
    modified_at = report_path.stat().st_mtime
    if manifest_path.exists() and manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ApplicationReportListItem(
                report_path=report_path,
                manifest_path=manifest_path,
                application_id=_extract_application_id_from_name(report_path),
                job_id=None,
                application_status=None,
                job_status=None,
                company=None,
                title=None,
                generated_at_utc=None,
                manifest_status="invalid",
                modified_at=max(modified_at, manifest_path.stat().st_mtime),
            )
        return _build_item_from_manifest(report_path=report_path, manifest_path=manifest_path, manifest=manifest)
    return ApplicationReportListItem(
        report_path=report_path,
        manifest_path=None,
        application_id=_extract_application_id_from_name(report_path),
        job_id=None,
        application_status=None,
        job_status=None,
        company=None,
        title=None,
        generated_at_utc=None,
        manifest_status="missing",
        modified_at=modified_at,
    )


def _build_item_from_manifest(
    *,
    report_path: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> ApplicationReportListItem:
    application = _dict_value(manifest, "application")
    job = _dict_value(manifest, "job")
    status = _dict_value(manifest, "status")
    return ApplicationReportListItem(
        report_path=report_path,
        manifest_path=manifest_path,
        application_id=_int_value(application.get("id")),
        job_id=_int_value(job.get("id") or application.get("job_id")),
        application_status=_str_value(status.get("application") or application.get("status")),
        job_status=_str_value(status.get("job") or job.get("status")),
        company=_str_value(job.get("company")),
        title=_str_value(job.get("title")),
        generated_at_utc=_str_value(manifest.get("generated_at_utc")),
        manifest_status="ok",
        modified_at=max(report_path.stat().st_mtime, manifest_path.stat().st_mtime),
    )


def _extract_application_id_from_name(path: Path) -> int | None:
    stem = path.stem
    prefix = "application-"
    if not stem.startswith(prefix):
        return None
    return _int_value(stem[len(prefix) :])


def _dict_value(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _int_value(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _str_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _value(value: object) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    return text if text else "-"
