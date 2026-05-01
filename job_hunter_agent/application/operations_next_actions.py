from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from job_hunter_agent.core.application_insights import classify_application_operational_insight


STATUS_PRIORITY = {
    "error_submit": 10,
    "authorized_submit": 20,
    "confirmed": 30,
    "ready_for_review": 40,
    "draft": 50,
}

TRACKED_STATUSES = tuple(STATUS_PRIORITY)


@dataclass(frozen=True)
class OperationNextAction:
    priority: int
    application_id: int
    job_id: int
    status: str
    title: str
    company: str
    reason_code: str
    command: str
    note: str


def build_operations_next_actions_from_repository(repository: object) -> list[OperationNextAction]:
    list_with_jobs = getattr(repository, "list_applications_with_jobs_by_status", None)
    applications_with_jobs: list[tuple[object, object | None]] = []
    for status in TRACKED_STATUSES:
        if list_with_jobs is not None:
            applications_with_jobs.extend(list_with_jobs(status))
            continue
        for application in repository.list_applications_by_status(status):
            applications_with_jobs.append((application, repository.get_job(application.job_id)))
    return build_operations_next_actions(applications_with_jobs)


def build_operations_next_actions(applications_with_jobs: Iterable[tuple[object, object | None]]) -> list[OperationNextAction]:
    actions: list[OperationNextAction] = []
    for application, job in applications_with_jobs:
        status = str(getattr(application, "status", ""))
        if status not in STATUS_PRIORITY:
            continue
        application_id = int(getattr(application, "id"))
        job_id = int(getattr(application, "job_id"))
        insight = classify_application_operational_insight(application)
        actions.append(
            OperationNextAction(
                priority=STATUS_PRIORITY[status],
                application_id=application_id,
                job_id=job_id,
                status=status,
                title=str(getattr(job, "title", "vaga nao encontrada") if job is not None else "vaga nao encontrada"),
                company=str(getattr(job, "company", "-") if job is not None else "-"),
                reason_code=insight.reason_code,
                command=_recommended_command(application_id=application_id, status=status),
                note=_recommended_note(status=status, reason_code=insight.reason_code),
            )
        )
    return sorted(actions, key=lambda action: (action.priority, action.application_id))


def render_operations_next_actions(actions: list[OperationNextAction]) -> str:
    if not actions:
        return "Nenhuma proxima acao operacional encontrada."
    lines = [f"Proximas acoes operacionais: {len(actions)}"]
    for action in actions:
        lines.extend(
            [
                f"- application_id={action.application_id} | job_id={action.job_id} | status={action.status}",
                f"  vaga={action.title} | empresa={action.company}",
                f"  motivo={action.reason_code}",
                f"  acao={action.note}",
                f"  comando={action.command}",
            ]
        )
    return "\n".join(lines)


def _recommended_command(*, application_id: int, status: str) -> str:
    if status == "error_submit":
        return f"python main.py applications diagnose --id {application_id}"
    if status == "authorized_submit":
        return f"python main.py applications submit --id {application_id} --dry-run"
    if status == "confirmed":
        return f"python main.py applications preflight --id {application_id} --dry-run"
    if status == "ready_for_review":
        return f"python main.py applications confirm --id {application_id}"
    if status == "draft":
        return f"python main.py applications prepare --id {application_id}"
    return f"python main.py applications diagnose --id {application_id}"


def _recommended_note(*, status: str, reason_code: str) -> str:
    if status == "error_submit":
        return "investigar erro antes de nova tentativa"
    if status == "authorized_submit":
        return "validar dry-run antes de submit real"
    if status == "confirmed":
        if reason_code == "pronto_para_envio":
            return "avaliar autorizacao humana explicita apos preflight"
        return "rodar preflight em dry-run antes de qualquer acao"
    if status == "ready_for_review":
        return "revisar manualmente antes de confirmar"
    if status == "draft":
        return "preparar candidatura para revisao humana"
    return "revisar manualmente"
