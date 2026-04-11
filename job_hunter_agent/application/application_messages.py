from __future__ import annotations

from job_hunter_agent.core.domain import JobApplication


def format_preflight_cli_result(*, detail: str, application_status: str) -> str:
    return f"Preflight: {detail} (status={application_status})"


def format_submit_cli_result(*, detail: str, application_status: str) -> str:
    return f"Submissao: {detail} (status={application_status})"


def format_preflight_requires_confirmed_status() -> str:
    return "preflight disponivel apenas para candidaturas confirmadas"


def format_preflight_unsupported_flow_blocked() -> str:
    return "preflight bloqueado: fluxo classificado como nao suportado"


def format_preflight_inspection_error(exc: Exception) -> str:
    return f"preflight real falhou ao inspecionar a pagina: {exc}"


def format_linkedin_preflight_ready(*, support_level: str) -> str:
    if support_level == "auto_supported":
        return "preflight ok: fluxo do LinkedIn com indicio de candidatura simplificada"
    return "preflight ok: vaga interna do LinkedIn pronta para futura automacao assistida"


def format_preflight_portal_not_supported(*, portal_name: str) -> str:
    return f"preflight bloqueado: portal {portal_name} ainda nao possui preflight suportado"


def format_preflight_readiness_incomplete(*, failures: list[str]) -> str:
    detail = "preflight bloqueado: prontidao operacional incompleta"
    if failures:
        return f"{detail} | faltando={'; '.join(failures)}"
    return detail


def format_submit_requires_authorized_status() -> str:
    return "submissao real disponivel apenas para candidaturas autorizadas"


def format_submit_portal_not_supported(*, portal_name: str) -> str:
    return f"submissao real bloqueada: portal {portal_name} ainda nao possui submit suportado"


def format_submit_readiness_incomplete(*, failures: list[str]) -> str:
    detail = "submissao real bloqueada: prontidao operacional incompleta"
    if failures:
        return f"{detail} | faltando={'; '.join(failures)}"
    return detail


def format_submit_unavailable_in_execution() -> str:
    return "submissao real indisponivel nesta execucao"


def format_submit_applicant_error(exc: Exception) -> str:
    return f"submissao real falhou ao executar o applicant: {exc}"


def format_submit_detail(*, detail: str, external_reference: str) -> str:
    normalized_detail = detail.strip() or "submissao real executada sem detalhe"
    if not external_reference.strip():
        return normalized_detail
    return f"{normalized_detail} | referencia={external_reference.strip()}"


def format_existing_application_for_job(*, application: JobApplication, job_id: int) -> str:
    return (
        f"Candidatura ja existe para a vaga: application_id={application.id} "
        f"status={application.status} job_id={job_id}"
    )


def format_job_not_approved_for_draft(*, job_id: int) -> str:
    return f"Vaga ainda nao foi aprovada para criar candidatura: id={job_id}"


def format_created_application_draft(*, application_id: int, job_id: int, status: str, support_level: str) -> str:
    return (
        f"Rascunho criado: application_id={application_id} job_id={job_id} "
        f"status={status} suporte={support_level}"
    )
