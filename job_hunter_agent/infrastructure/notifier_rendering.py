from __future__ import annotations

from job_hunter_agent.llm.application_priority import extract_application_priority_level
from job_hunter_agent.core.application_insights import classify_application_operational_insight
from job_hunter_agent.core.domain import JobApplication, JobPosting
from job_hunter_agent.llm.job_requirements import (
    extract_job_requirement_signals,
    format_job_requirement_summary,
)
from job_hunter_agent.infrastructure.repository import JobRepository
from job_hunter_agent.llm.review_rationale import StructuredReviewRationale, render_review_rationale


def summarize_application_notes(notes: str, *, max_chars: int = 500) -> str:
    normalized_lines = [line.strip() for line in notes.splitlines() if line.strip()]
    if not normalized_lines:
        return "Nenhuma"
    preferred: list[str] = []
    for prefix in (
        "rascunho criado apos aprovacao humana",
        "sinais estruturados:",
        "prioridade sugerida:",
    ):
        for line in reversed(normalized_lines):
            if line.lower().startswith(prefix):
                preferred.append(line)
                break
    if not preferred:
        preferred = normalized_lines[-3:]
    unique_lines: list[str] = []
    for line in preferred:
        if line not in unique_lines:
            unique_lines.append(line)
    summary = "\n".join(unique_lines)
    if len(summary) <= max_chars:
        return summary
    return summary[: max_chars - 3].rstrip() + "..."


def summarize_application_operation(application: JobApplication, *, max_chars: int = 500) -> str:
    lines: list[str] = []
    if application.last_preflight_detail:
        lines.append(f"Preflight: {application.last_preflight_detail}")
    if application.last_submit_detail:
        lines.append(f"Submit: {application.last_submit_detail}")
    if application.last_error:
        lines.append(f"Erro: {application.last_error}")
    if not lines:
        return "Nenhuma"
    summary = "\n".join(lines)
    if len(summary) <= max_chars:
        return summary
    return summary[: max_chars - 3].rstrip() + "..."


def build_job_card_message(
    job: JobPosting,
    structured_rationale: StructuredReviewRationale | None = None,
) -> str:
    return (
        f"*{job.title}*\n"
        f"Empresa: {job.company}\n"
        f"Local: {job.location} | Modalidade: {job.work_mode}\n"
        f"Salario: {job.salary_text}\n"
        f"Relevancia: {job.relevance}/10\n"
        f"Motivo: {render_review_rationale(job, structured_rationale)}\n"
        f"Resumo: {job.summary}\n"
        f"[Abrir vaga]({job.url})"
    )


def build_missing_job_reply(job_id: int) -> str:
    return f"Vaga nao encontrada ou ja removida. id={job_id}"


def build_missing_application_reply(application_id: int) -> str:
    return f"Candidatura nao encontrada ou ja removida. id={application_id}"


def build_application_queue_message(repository: JobRepository) -> str:
    summary = repository.application_summary()
    tracked_statuses = ("draft", "ready_for_review", "confirmed", "authorized_submit", "error_submit")
    preview_lines: list[str] = []
    tracked_applications: list[JobApplication] = []
    for status in tracked_statuses:
        applications = _sort_applications_by_priority(repository.list_applications_by_status(status))
        tracked_applications.extend(applications)
        for application in applications[:3]:
            preview_lines.append(build_application_preview_line(repository, application))
    lines = [
        "Candidaturas:",
        f"Total: {summary['total']}",
        f"Rascunhos: {summary['draft']}",
        f"Prontas para revisao: {summary['ready_for_review']}",
        f"Confirmadas: {summary['confirmed']}",
        f"Autorizadas para envio: {summary['authorized_submit']}",
        f"Enviadas: {summary['submitted']}",
        f"Com erro: {summary['error_submit']}",
        f"Canceladas: {summary['cancelled']}",
    ]
    operational_summary = summarize_operational_classifications(tracked_applications)
    if operational_summary:
        lines.append("")
        lines.append("Classificacao operacional:")
        lines.extend(operational_summary)
    if preview_lines:
        lines.append("")
        lines.append("Fila atual:")
        lines.extend(preview_lines)
    else:
        lines.append("")
        lines.append("Nao ha rascunhos ou candidaturas em andamento.")
    return "\n".join(lines)


def build_application_preview_line(repository: JobRepository, application: JobApplication) -> str:
    job = repository.get_job(application.job_id)
    priority = extract_application_priority_level(application.notes)
    operational = classify_application_operational_insight(application)
    if not job:
        return (
            f"{application.job_id}: vaga ausente "
            f"[{application.status} | prioridade {priority} | op={operational.reason_code}]"
        )
    return (
        f"{job.id}: {job.title} - {job.company} "
        f"[{application.status} | {application.support_level} | prioridade {priority} | op={operational.reason_code}]"
    )


def build_application_card_message(repository: JobRepository, application: JobApplication) -> str:
    job = repository.get_job(application.job_id)
    priority = extract_application_priority_level(application.notes)
    requirement_summary = format_job_requirement_summary(extract_job_requirement_signals(application.notes))
    summarized_notes = summarize_application_notes(application.notes or "")
    operation_summary = summarize_application_operation(application)
    operational = classify_application_operational_insight(application)
    if not job:
        return (
            f"Candidatura {application.id}\n"
            f"Job id: {application.job_id}\n"
            f"Status: {application.status}\n"
            f"Suporte: {application.support_level}\n"
            f"Prioridade: {priority}\n"
            f"Classificacao operacional: {operational.classification} | {operational.summary}\n"
            f"Sinais: {requirement_summary}\n"
            f"Racional: {application.support_rationale or 'Nao informado'}\n"
            f"Contexto: {summarized_notes}\n"
            f"Operacao: {operation_summary}"
        )
    return (
        f"Candidatura {application.id}\n"
        f"Vaga: {job.title}\n"
        f"Empresa: {job.company}\n"
        f"Status: {application.status}\n"
        f"Suporte: {application.support_level}\n"
        f"Prioridade: {priority}\n"
        f"Classificacao operacional: {operational.classification} | {operational.summary}\n"
        f"Sinais: {requirement_summary}\n"
        f"Racional: {application.support_rationale or 'Nao informado'}\n"
        f"Contexto: {summarized_notes}\n"
        f"Operacao: {operation_summary}\n"
        f"Abrir vaga: {job.url}"
    )


def build_application_action_rows(application: JobApplication, button_factory) -> list[list[object]]:
    if application.status == "draft":
        return [
            [
                button_factory("Preparar", callback_data=f"app_prepare:{application.id}"),
                button_factory("Cancelar", callback_data=f"app_cancel:{application.id}"),
            ]
        ]
    if application.status == "ready_for_review":
        return [
            [
                button_factory("Confirmar", callback_data=f"app_confirm:{application.id}"),
                button_factory("Cancelar", callback_data=f"app_cancel:{application.id}"),
            ]
        ]
    if application.status == "confirmed":
        return [
            [
                button_factory("Validar fluxo", callback_data=f"app_preflight:{application.id}"),
                button_factory("Autorizar envio", callback_data=f"app_authorize:{application.id}"),
                button_factory("Cancelar", callback_data=f"app_cancel:{application.id}"),
            ]
        ]
    if application.status == "authorized_submit":
        return [
            [
                button_factory("Enviar candidatura", callback_data=f"app_submit:{application.id}"),
                button_factory("Cancelar", callback_data=f"app_cancel:{application.id}"),
            ]
        ]
    if application.status == "error_submit":
        return [
            [
                button_factory("Validar fluxo", callback_data=f"app_preflight:{application.id}"),
                button_factory("Reautorizar", callback_data=f"app_authorize:{application.id}"),
                button_factory("Cancelar", callback_data=f"app_cancel:{application.id}"),
            ]
        ]
    return []


def _sort_applications_by_priority(applications: list[JobApplication]) -> list[JobApplication]:
    priority_order = {"alta": 0, "media": 1, "baixa": 2}
    return sorted(
        applications,
        key=lambda application: (priority_order.get(extract_application_priority_level(application.notes), 3), application.id),
    )


def summarize_operational_classifications(applications: list[JobApplication]) -> list[str]:
    if not applications:
        return []
    counts: dict[str, int] = {}
    for application in applications:
        insight = classify_application_operational_insight(application)
        if insight.reason_code in {"sem_detalhe_operacional", "nao_classificado"}:
            continue
        counts[insight.reason_code] = counts.get(insight.reason_code, 0) + 1
    if not counts:
        return []
    ordered_labels = (
        ("pronto_para_envio", "pronto_para_envio"),
        ("perguntas_adicionais", "perguntas_adicionais"),
        ("similar_jobs", "similar_jobs"),
        ("candidatura_externa", "candidatura_externa"),
        ("vaga_expirada", "vaga_expirada"),
        ("no_apply_cta", "no_apply_cta"),
        ("fluxo_inconclusivo", "fluxo_inconclusivo"),
        ("bloqueio_funcional", "bloqueio_funcional"),
        ("submitted", "submitted"),
    )
    lines: list[str] = []
    emitted: set[str] = set()
    for key, label in ordered_labels:
        if key in counts:
            lines.append(f"- {label}={counts[key]}")
            emitted.add(key)
    for key in sorted(counts):
        if key not in emitted:
            lines.append(f"- {key}={counts[key]}")
    return lines
