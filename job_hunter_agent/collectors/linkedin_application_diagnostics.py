from __future__ import annotations

from job_hunter_agent.collectors.linkedin_application_state import (
    LinkedInApplicationPageState,
    LinkedInJobPageReadiness,
    describe_linkedin_job_page_readiness,
    describe_linkedin_modal_blocker,
)

BLOCKED_FUNCTIONAL = "bloqueio_funcional"
INCONCLUSIVE_STATE = "estado_inconclusivo"
PORTAL_ERROR = "erro_portal"
UNEXPECTED_FAILURE = "falha_inesperada"
KNOWN_OPERATIONAL_CATEGORIES = {
    BLOCKED_FUNCTIONAL,
    INCONCLUSIVE_STATE,
    PORTAL_ERROR,
    UNEXPECTED_FAILURE,
}


def _format_operational_detail(category: str, message: str) -> str:
    return f"{category}: {message}"


def extract_operational_detail_category(detail: str) -> str:
    category, _, _ = str(detail or "").partition(": ")
    return category if category in KNOWN_OPERATIONAL_CATEGORIES else ""


def build_preflight_blocked_readiness_detail(readiness: LinkedInJobPageReadiness) -> str:
    return _format_operational_detail(
        BLOCKED_FUNCTIONAL,
        f"preflight real bloqueado: {describe_linkedin_job_page_readiness(readiness)}",
    )


def build_preflight_inconclusive_modal_not_open_detail() -> str:
    return _format_operational_detail(
        INCONCLUSIVE_STATE,
        (
            "preflight real inconclusivo: CTA de candidatura simplificada encontrado, "
            "mas modal nao abriu"
        ),
    )


def build_submit_blocked_readiness_detail(readiness: LinkedInJobPageReadiness) -> str:
    return _format_operational_detail(
        BLOCKED_FUNCTIONAL,
        f"submissao real bloqueada: {describe_linkedin_job_page_readiness(readiness)}",
    )


def build_submit_missing_easy_apply_detail() -> str:
    return _format_operational_detail(
        BLOCKED_FUNCTIONAL,
        "submissao real bloqueada: CTA de candidatura simplificada nao encontrado",
    )


def build_submit_flow_not_ready_detail(state: LinkedInApplicationPageState) -> str:
    return _format_operational_detail(
        INCONCLUSIVE_STATE,
        (
            "submissao real bloqueada: fluxo nao chegou ao botao de envio"
            f" | bloqueio={describe_linkedin_modal_blocker(state)}"
        ),
    )


def build_submit_not_confirmed_detail() -> str:
    return _format_operational_detail(
        PORTAL_ERROR,
        "submissao real falhou: clique final de envio nao confirmou sucesso",
    )


def build_submit_success_detail() -> str:
    return "submissao real concluida no LinkedIn"


def build_submit_closed_page_detail() -> str:
    return _format_operational_detail(
        PORTAL_ERROR,
        "submissao real interrompida: pagina do LinkedIn foi fechada durante a automacao",
    )


def build_submit_unexpected_failure_detail(exc: Exception) -> str:
    return _format_operational_detail(
        UNEXPECTED_FAILURE,
        f"submissao real falhou com erro inesperado: {exc}",
    )
