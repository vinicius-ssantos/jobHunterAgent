from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from job_hunter_agent.application.application_report import DEFAULT_APPLICATION_REPORTS_DIR


REQUIRED_MANIFEST_FIELDS = (
    "application",
    "job",
    "status",
    "support",
    "report_path",
    "manifest_path",
    "safety",
    "generated_at_utc",
)

EXPECTED_SAFETY_FLAGS = {
    "read_only": True,
    "uses_llm": False,
    "runs_preflight": False,
    "runs_submit": False,
    "changes_status": False,
}


@dataclass(frozen=True)
class ApplicationReportValidationIssue:
    level: str
    path: Path
    message: str


@dataclass(frozen=True)
class ApplicationReportValidationResult:
    reports_dir: Path
    ok_count: int
    warning_count: int
    error_count: int
    issues: tuple[ApplicationReportValidationIssue, ...]


def validate_application_reports(
    *,
    reports_dir: Path = DEFAULT_APPLICATION_REPORTS_DIR,
    strict: bool = False,
) -> ApplicationReportValidationResult:
    issues: list[ApplicationReportValidationIssue] = []
    ok_count = 0
    if not reports_dir.exists():
        issues.append(ApplicationReportValidationIssue("warning", reports_dir, "diretorio de relatorios nao existe"))
        return _build_result(reports_dir=reports_dir, ok_count=0, issues=issues)

    markdown_paths = {path.with_suffix(""): path for path in reports_dir.glob("*.md") if path.is_file()}
    manifest_paths = {path.with_suffix(""): path for path in reports_dir.glob("*.json") if path.is_file()}
    all_stems = sorted(set(markdown_paths) | set(manifest_paths), key=lambda path: path.name)

    for stem in all_stems:
        report_path = markdown_paths.get(stem)
        manifest_path = manifest_paths.get(stem)
        if report_path is None and manifest_path is not None:
            issues.append(
                ApplicationReportValidationIssue(
                    _pair_issue_level(strict),
                    manifest_path,
                    "manifesto JSON sem Markdown correspondente",
                )
            )
            continue
        if report_path is not None and manifest_path is None:
            issues.append(
                ApplicationReportValidationIssue(
                    _pair_issue_level(strict),
                    report_path,
                    "Markdown sem manifesto JSON correspondente",
                )
            )
            continue
        if report_path is None or manifest_path is None:
            continue
        manifest_issues = _validate_manifest(report_path=report_path, manifest_path=manifest_path)
        if manifest_issues:
            issues.extend(manifest_issues)
            continue
        ok_count += 1

    return _build_result(reports_dir=reports_dir, ok_count=ok_count, issues=issues)


def render_application_reports_validation(
    *,
    reports_dir: Path = DEFAULT_APPLICATION_REPORTS_DIR,
    strict: bool = False,
) -> str:
    result = validate_application_reports(reports_dir=reports_dir, strict=strict)
    lines = [
        f"Validacao de relatorios A-F em {result.reports_dir}:",
        f"- ok={result.ok_count}",
        f"- warnings={result.warning_count}",
        f"- errors={result.error_count}",
        f"- strict={str(strict).lower()}",
    ]
    if result.issues:
        lines.append("Problemas:")
        for issue in result.issues:
            lines.append(f"- {issue.level}: {issue.path}: {issue.message}")
    return "\n".join(lines)


def _validate_manifest(*, report_path: Path, manifest_path: Path) -> list[ApplicationReportValidationIssue]:
    issues: list[ApplicationReportValidationIssue] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [
            ApplicationReportValidationIssue(
                "error",
                manifest_path,
                f"manifesto JSON invalido: {error}",
            )
        ]
    if not isinstance(manifest, dict):
        return [ApplicationReportValidationIssue("error", manifest_path, "manifesto JSON deve ser um objeto")]

    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            issues.append(ApplicationReportValidationIssue("error", manifest_path, f"campo obrigatorio ausente: {field}"))

    report_path_value = _str_value(manifest.get("report_path"))
    manifest_path_value = _str_value(manifest.get("manifest_path"))
    if report_path_value is not None and Path(report_path_value) != report_path:
        issues.append(ApplicationReportValidationIssue("error", manifest_path, "report_path nao aponta para o Markdown validado"))
    if manifest_path_value is not None and Path(manifest_path_value) != manifest_path:
        issues.append(ApplicationReportValidationIssue("error", manifest_path, "manifest_path nao aponta para o JSON validado"))

    safety = manifest.get("safety")
    if not isinstance(safety, dict):
        issues.append(ApplicationReportValidationIssue("error", manifest_path, "safety deve ser um objeto"))
        return issues
    for key, expected in EXPECTED_SAFETY_FLAGS.items():
        if safety.get(key) is not expected:
            issues.append(
                ApplicationReportValidationIssue(
                    "error",
                    manifest_path,
                    f"flag de safety invalida: {key}={safety.get(key)!r}, esperado {expected!r}",
                )
            )
    return issues


def _build_result(
    *,
    reports_dir: Path,
    ok_count: int,
    issues: list[ApplicationReportValidationIssue],
) -> ApplicationReportValidationResult:
    warning_count = sum(1 for issue in issues if issue.level == "warning")
    error_count = sum(1 for issue in issues if issue.level == "error")
    return ApplicationReportValidationResult(
        reports_dir=reports_dir,
        ok_count=ok_count,
        warning_count=warning_count,
        error_count=error_count,
        issues=tuple(issues),
    )


def _pair_issue_level(strict: bool) -> str:
    return "error" if strict else "warning"


def _str_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
