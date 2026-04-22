from __future__ import annotations

from datetime import datetime
from pathlib import Path

from job_hunter_agent.core.application_insights import (
    classify_application_operational_insight,
    classify_operational_detail,
    describe_manual_review_need,
)
from job_hunter_agent.core.operational_policy import get_runtime_operational_policy


def render_application_list(*, applications_with_jobs: list[tuple[object, object | None]], status: str | None) -> str:
    lines: list[str] = []
    for application, job in applications_with_jobs:
        job_label = f"{job.title} | {job.company}" if job is not None else f"job_id={application.job_id}"
        lines.append(
            f"{application.id}: {application.status} | {job_label} | suporte={application.support_level} "
            f"| op={classify_application_operational_insight(application).reason_code}"
        )
    if not lines:
        filter_text = status if status is not None else "todos"
        return f"Nenhuma candidatura encontrada para status={filter_text}."
    return "\n".join([f"Candidaturas listadas: {len(lines)}"] + lines)


def render_job_list(*, jobs: list[object], status: str | None) -> str:
    lines = [
        f"{job.id}: {job.status} | {job.title} | {job.company} | "
        f"relevancia={job.relevance} | modalidade={job.work_mode}"
        for job in jobs
    ]
    if not lines:
        filter_text = status if status is not None else "todos"
        return f"Nenhuma vaga encontrada para status={filter_text}."
    return "\n".join([f"Vagas listadas: {len(lines)}"] + lines)


def render_job_detail(*, job: object, application: object | None, events: list[object]) -> str:
    lines = [
        f"id={job.id}",
        f"status={job.status}",
        f"titulo={job.title}",
        f"empresa={job.company}",
        f"local={job.location}",
        f"modalidade={job.work_mode}",
        f"salario={job.salary_text}",
        f"relevancia={job.relevance}",
        f"fonte={job.source_site}",
        f"url={job.url}",
        f"rationale={job.rationale}",
        f"summary={job.summary}",
        f"application_id={application.id if application is not None else '-'}",
        f"application_status={application.status if application is not None else '-'}",
    ]
    if events:
        lines.append("eventos_recentes:")
        lines.extend(_render_event_lines(events))
    return "\n".join(lines)


def summarize_operational_counts(*, applications: list[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for application in applications:
        reason_code = classify_application_operational_insight(application).reason_code
        if reason_code in {"sem_detalhe_operacional", "nao_classificado"}:
            continue
        counts[reason_code] = counts.get(reason_code, 0) + 1
    return counts


def render_status_overview(
    *,
    job_summary: dict[str, int],
    application_summary: dict[str, int],
    operational_counts: dict[str, int],
) -> str:
    lines = [
        "Resumo operacional:",
        "vagas:",
        f"- total={job_summary['total']}",
        f"- collected={job_summary['collected']}",
        f"- approved={job_summary['approved']}",
        f"- rejected={job_summary['rejected']}",
        f"- error_collect={job_summary['error_collect']}",
        "candidaturas:",
        f"- total={application_summary['total']}",
        f"- draft={application_summary['draft']}",
        f"- ready_for_review={application_summary['ready_for_review']}",
        f"- confirmed={application_summary['confirmed']}",
        f"- authorized_submit={application_summary['authorized_submit']}",
        f"- submitted={application_summary['submitted']}",
        f"- error_submit={application_summary['error_submit']}",
        f"- cancelled={application_summary['cancelled']}",
    ]
    if operational_counts:
        lines.append("operacao:")
        for key in get_runtime_operational_policy().operational_summary_order:
            if key in operational_counts:
                lines.append(f"- {key}={operational_counts[key]}")
    return "\n".join(lines)


def render_application_events(*, application_id: int, events: list[object]) -> str:
    if not events:
        return f"Nenhum evento encontrado para candidatura: id={application_id}"
    return "\n".join(
        [f"Eventos da candidatura {application_id}: {len(events)}"] + _render_event_lines(events)
    )


def render_application_detail(*, application: object, job: object | None, events: list[object]) -> str:
    job_title = job.title if job is not None else "vaga nao encontrada"
    job_company = job.company if job is not None else "-"
    job_url = job.url if job is not None else "-"
    insight = classify_application_operational_insight(application)
    lines = [
        f"id={application.id}",
        f"status={application.status}",
        f"job_id={application.job_id}",
        f"vaga={job_title}",
        f"empresa={job_company}",
        f"suporte={application.support_level}",
        f"classificacao_operacional={insight.classification} | motivo={insight.reason_code}",
        f"url={job_url}",
        f"last_preflight_detail={application.last_preflight_detail or '-'}",
        f"last_submit_detail={application.last_submit_detail or '-'}",
        f"last_error={application.last_error or '-'}",
        f"submitted_at={application.submitted_at or '-'}",
        f"notes={application.notes or '-'}",
    ]
    if application.support_level == "manual_review":
        lines.append(f"manual_review_detail={describe_manual_review_need(application)}")
    if events:
        lines.append("eventos_recentes:")
        lines.extend(_render_event_lines(events))
    return "\n".join(lines)


def render_failure_artifacts(*, artifacts_dir: Path, files: list[Path], limit: int) -> str:
    if not artifacts_dir.exists():
        return f"Nenhum diretorio de artefatos encontrado: {artifacts_dir}"
    if not files:
        return f"Nenhum artefato de falha encontrado em: {artifacts_dir}"
    lines = [f"Artefatos recentes: {min(len(files), limit)}"]
    for path in files[:limit]:
        timestamp = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        lines.append(f"{timestamp} | {path.name}")
    return "\n".join(lines)


def render_execution_summary(*, events: list[object]) -> str:
    preflight_count = 0
    submit_count = 0
    block_counts: dict[str, int] = {}
    for event in events:
        if event.event_type in {"preflight_ready", "preflight_manual_review", "preflight_blocked", "preflight_error"}:
            preflight_count += 1
        if event.event_type in {"submit_submitted", "submit_error"}:
            submit_count += 1
        if event.event_type in {"preflight_blocked", "submit_error"}:
            reason_code = classify_operational_detail(event.detail).reason_code
            if reason_code not in {"sem_detalhe_operacional", "nao_classificado"}:
                block_counts[reason_code] = block_counts.get(reason_code, 0) + 1
    lines = [
        "Execucao operacional:",
        f"- preflights_concluidos={preflight_count}",
        f"- submits_concluidos={submit_count}",
    ]
    if block_counts:
        lines.append("- bloqueios_por_tipo:")
        for key in sorted(block_counts):
            lines.append(f"  - {key}={block_counts[key]}")
    else:
        lines.append("- bloqueios_por_tipo=nenhum")
    return "\n".join(lines)


def _render_event_lines(events: list[object]) -> list[str]:
    return [
        f"- {event.created_at or '-'} | {event.event_type} | "
        f"{event.from_status or '-'} -> {event.to_status or '-'} | "
        f"{event.detail or '-'}"
        for event in events
    ]
