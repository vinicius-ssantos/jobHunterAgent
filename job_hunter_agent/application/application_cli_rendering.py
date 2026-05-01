from __future__ import annotations

from datetime import datetime
from pathlib import Path

from job_hunter_agent.core.application_insights import (
    classify_application_operational_insight,
    classify_operational_detail,
    describe_manual_review_need,
)
from job_hunter_agent.core.events import DomainEvent, event_to_dict
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


def render_operations_report(
    *,
    since: str,
    job_summary: dict[str, int],
    application_summary: dict[str, int],
    operational_counts: dict[str, int],
    events: list[object],
) -> str:
    lines = [
        "Relatorio operacional local:",
        f"janela_desde={since}",
        "snapshot_atual:",
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
        lines.append("operacao_atual:")
        for key in get_runtime_operational_policy().operational_summary_order:
            if key in operational_counts:
                lines.append(f"- {key}={operational_counts[key]}")
    lines.append("resumo_da_janela:")
    lines.extend(render_execution_summary(events=events).splitlines()[1:])
    lines.append("eventos_recentes:")
    if events:
        lines.extend(_render_event_lines(events[-10:]))
    else:
        lines.append("- nenhum")
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


def render_application_diagnosis(
    *,
    application: object,
    job: object | None,
    events: list[object],
    domain_events: tuple[DomainEvent, ...] = (),
    domain_events_enabled: bool = False,
) -> str:
    job_title = job.title if job is not None else "vaga nao encontrada"
    job_company = job.company if job is not None else "-"
    job_status = job.status if job is not None else "-"
    job_source = job.source_site if job is not None else "-"
    job_url = job.url if job is not None else "-"
    insight = classify_application_operational_insight(application)
    next_action = _recommend_application_next_action(application=application, insight_reason=insight.reason_code)
    lines = [
        f"Diagnostico da candidatura {application.id}",
        "candidatura:",
        f"- id={application.id}",
        f"- status={application.status}",
        f"- job_id={application.job_id}",
        f"- suporte={application.support_level}",
        f"- classificacao_operacional={insight.classification}",
        f"- motivo_operacional={insight.reason_code}",
        "vaga:",
        f"- titulo={job_title}",
        f"- empresa={job_company}",
        f"- status={job_status}",
        f"- fonte={job_source}",
        f"- url={job_url}",
        "preflight_submit:",
        f"- last_preflight_detail={application.last_preflight_detail or '-'}",
        f"- last_submit_detail={application.last_submit_detail or '-'}",
        f"- last_error={application.last_error or '-'}",
        f"- submitted_at={application.submitted_at or '-'}",
        f"- notes={application.notes or '-'}",
        "proxima_acao:",
        f"- {next_action}",
    ]
    if application.support_level == "manual_review":
        lines.extend(["revisao_manual:", f"- {describe_manual_review_need(application)}"])
    lines.append("eventos_sqlite_recentes:")
    if events:
        lines.extend(_render_event_lines(events))
    else:
        lines.append("- nenhum")
    lines.append("domain_events_recentes:")
    if not domain_events_enabled:
        lines.append("- indisponivel_ou_desabilitado")
    elif domain_events:
        lines.extend(_render_domain_event_lines(domain_events))
    else:
        lines.append("- nenhum")
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
    transitions: dict[tuple[str, str], int] = {}
    for event in events:
        if event.event_type in {"preflight_ready", "preflight_manual_review", "preflight_blocked", "preflight_error"}:
            preflight_count += 1
        if event.event_type in {"submit_submitted", "submit_error"}:
            submit_count += 1
        if event.event_type in {"preflight_blocked", "submit_error"}:
            reason_code = classify_operational_detail(event.detail).reason_code
            if reason_code not in {"sem_detalhe_operacional", "nao_classificado"}:
                block_counts[reason_code] = block_counts.get(reason_code, 0) + 1
        from_status = (event.from_status or "").strip()
        to_status = (event.to_status or "").strip()
        if from_status and to_status and from_status != to_status:
            key = (from_status, to_status)
            transitions[key] = transitions.get(key, 0) + 1
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
    draft_to_ready = transitions.get(("draft", "ready_for_review"), 0)
    ready_to_confirmed = transitions.get(("ready_for_review", "confirmed"), 0)
    confirmed_to_authorized = transitions.get(("confirmed", "authorized_submit"), 0)
    authorized_to_submitted = transitions.get(("authorized_submit", "submitted"), 0)
    lines.extend(
        [
            "- conversoes_por_etapa:",
            f"- draft_para_ready_for_review={draft_to_ready}",
            f"- ready_for_review_para_confirmed={ready_to_confirmed}",
            f"- confirmed_para_authorized_submit={confirmed_to_authorized}",
            f"- authorized_submit_para_submitted={authorized_to_submitted}",
            (
                f"- taxa_authorized_submit_para_submitted="
                f"{_render_conversion_ratio(authorized_to_submitted, confirmed_to_authorized)}"
            ),
        ]
    )
    return "\n".join(lines)


def _recommend_application_next_action(*, application: object, insight_reason: str) -> str:
    application_id = application.id
    status = application.status
    if status == "draft":
        return f"preparar revisao: python main.py applications prepare --id {application_id}"
    if status == "ready_for_review":
        return f"confirmar ou cancelar apos revisao humana: python main.py applications confirm --id {application_id}"
    if status == "confirmed":
        if insight_reason == "pronto_para_envio":
            return f"autorizar envio se revisao humana estiver ok: python main.py applications authorize --id {application_id}"
        return f"rodar preflight real ou dry-run: python main.py applications preflight --id {application_id}"
    if status == "authorized_submit":
        return f"executar submit controlado ou dry-run: python main.py applications submit --id {application_id}"
    if status == "error_submit":
        return "investigar bloqueio: revisar last_error, artifacts e domain-events antes de tentar novamente"
    if status == "submitted":
        return "nenhuma acao operacional pendente: candidatura ja enviada"
    if status == "cancelled":
        return "nenhuma acao automatica: candidatura cancelada"
    return "revisar estado manualmente antes de executar nova transicao"


def _render_conversion_ratio(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "n/a"
    ratio = (numerator / denominator) * 100
    return f"{ratio:.1f}%"


def _render_event_lines(events: list[object]) -> list[str]:
    return [
        f"- {event.created_at or '-'} | {event.event_type} | "
        f"{event.from_status or '-'} -> {event.to_status or '-'} | "
        f"{event.detail or '-'}"
        for event in events
    ]


def _render_domain_event_lines(events: tuple[DomainEvent, ...]) -> list[str]:
    lines: list[str] = []
    for event in events:
        payload = event_to_dict(event)
        interesting_keys = [
            "application_id",
            "job_id",
            "status",
            "application_status",
            "outcome",
            "reason",
            "retryable",
            "portal",
        ]
        details = " ".join(
            f"{key}={payload[key]}" for key in interesting_keys if key in payload and payload[key] not in {None, ""}
        )
        suffix = f" {details}" if details else ""
        lines.append(
            f"- {event.occurred_at} | {event.event_type} | "
            f"correlation_id={event.correlation_id or '-'}{suffix}"
        )
    return lines
