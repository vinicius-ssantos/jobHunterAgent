from __future__ import annotations

from job_hunter_agent.domain import JobApplication, JobPosting


def resolve_review_action(job: JobPosting, action: str) -> tuple[str | None, str]:
    if action == "approve":
        if job.status == "approved":
            return None, f"Vaga ja estava aprovada: {job.title} - {job.company}"
        if job.status == "rejected":
            return None, f"Vaga ja estava rejeitada: {job.title} - {job.company}"
        return "approved", f"Vaga aprovada: {job.title} - {job.company}"

    if action == "reject":
        if job.status == "rejected":
            return None, f"Vaga ja estava rejeitada: {job.title} - {job.company}"
        if job.status == "approved":
            return None, f"Vaga ja estava aprovada: {job.title} - {job.company}"
        return "rejected", f"Vaga ignorada: {job.title} - {job.company}"

    return None, "Acao de revisao invalida."


def resolve_application_preflight_request(application: JobApplication) -> tuple[bool, str]:
    if application.status == "confirmed":
        return True, f"Executando preflight da candidatura: id={application.id}"
    if application.status == "authorized_submit":
        return False, f"Candidatura ja foi autorizada para envio: id={application.id}"
    if application.status == "cancelled":
        return False, f"Candidatura ja estava cancelada: id={application.id}"
    if application.status == "error_submit":
        return False, f"Candidatura esta em erro de submissao: id={application.id}"
    return False, f"Candidatura ainda nao foi confirmada para preflight: id={application.id}"


def resolve_application_submit_request(application: JobApplication) -> tuple[bool, str]:
    if application.status == "authorized_submit":
        return True, f"Executando submissao real da candidatura: id={application.id}"
    if application.status == "submitted":
        return False, f"Candidatura ja foi enviada: id={application.id}"
    if application.status == "cancelled":
        return False, f"Candidatura ja estava cancelada: id={application.id}"
    if application.status == "error_submit":
        return False, f"Candidatura esta em erro de submissao: id={application.id}"
    return False, f"Candidatura ainda nao foi autorizada para envio: id={application.id}"


def resolve_application_action(application: JobApplication, action: str) -> tuple[str | None, str]:
    if action == "app_prepare":
        if application.status == "draft":
            return "ready_for_review", f"Candidatura pronta para revisao: id={application.id}"
        if application.status == "ready_for_review":
            return None, f"Candidatura ja estava pronta para revisao: id={application.id}"
        if application.status == "confirmed":
            return None, f"Candidatura ja estava confirmada: id={application.id}"
        if application.status == "cancelled":
            return None, f"Candidatura ja estava cancelada: id={application.id}"
    if action == "app_confirm":
        if application.status == "ready_for_review":
            return "confirmed", f"Candidatura confirmada: id={application.id}"
        if application.status == "draft":
            return None, f"Candidatura ainda nao foi preparada para revisao: id={application.id}"
        if application.status == "confirmed":
            return None, f"Candidatura ja estava confirmada: id={application.id}"
        if application.status == "cancelled":
            return None, f"Candidatura ja estava cancelada: id={application.id}"
    if action == "app_cancel":
        if application.status == "cancelled":
            return None, f"Candidatura ja estava cancelada: id={application.id}"
        if application.status in {"draft", "ready_for_review", "confirmed", "authorized_submit"}:
            return "cancelled", f"Candidatura cancelada: id={application.id}"
    if action == "app_authorize":
        if application.status == "confirmed":
            return "authorized_submit", f"Candidatura autorizada para envio: id={application.id}"
        if application.status == "authorized_submit":
            return None, f"Candidatura ja estava autorizada para envio: id={application.id}"
        if application.status == "ready_for_review":
            return None, f"Candidatura ainda nao foi confirmada: id={application.id}"
        if application.status == "draft":
            return None, f"Candidatura ainda nao foi preparada para envio: id={application.id}"
        if application.status == "cancelled":
            return None, f"Candidatura ja estava cancelada: id={application.id}"
    return None, "Acao de candidatura invalida."

