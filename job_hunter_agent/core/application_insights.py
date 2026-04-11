from __future__ import annotations

from dataclasses import dataclass

from job_hunter_agent.core.domain import JobApplication


@dataclass(frozen=True)
class ApplicationOperationalInsight:
    classification: str
    reason_code: str
    summary: str
    source_detail: str = ""


def classify_operational_detail(detail: str) -> ApplicationOperationalInsight:
    source_detail = detail.strip()
    if not source_detail:
        return ApplicationOperationalInsight(
            classification="unknown",
            reason_code="sem_detalhe_operacional",
            summary="sem detalhe operacional",
        )

    lowered = source_detail.lower()

    if "readiness=listing_redirect" in lowered or "similar-jobs" in lowered or "similar jobs" in lowered:
        return ApplicationOperationalInsight(
            classification="blocked",
            reason_code="similar_jobs",
            summary="redirecionada para similar jobs",
            source_detail=source_detail,
        )
    if "perguntas_pendentes=" in lowered or "perguntas_obrigatorias" in lowered or "perguntas_nao_mapeadas" in lowered:
        return ApplicationOperationalInsight(
            classification="manual_review",
            reason_code="perguntas_adicionais",
            summary="perguntas adicionais pendentes",
            source_detail=source_detail,
        )
    if "readiness=expired" in lowered:
        return ApplicationOperationalInsight(
            classification="blocked",
            reason_code="vaga_expirada",
            summary="vaga expirada ou indisponivel",
            source_detail=source_detail,
        )
    if "readiness=no_apply_cta" in lowered:
        summary = "cta de candidatura ausente"
        reason = "no_apply_cta"
        if "externa" in lowered or "site da empresa" in lowered:
            summary = "candidatura externa"
            reason = "candidatura_externa"
        return ApplicationOperationalInsight(
            classification="blocked",
            reason_code=reason,
            summary=summary,
            source_detail=source_detail,
        )
    if "pronto_para_envio=sim" in lowered or "ok: fluxo pronto para submissao assistida" in lowered:
        return ApplicationOperationalInsight(
            classification="ready",
            reason_code="pronto_para_envio",
            summary="fluxo pronto para envio",
            source_detail=source_detail,
        )
    if "preflight real ok" in lowered or "cta encontrado" in lowered:
        return ApplicationOperationalInsight(
            classification="manual_review",
            reason_code="cta_detectado",
            summary="cta detectado; validar fluxo",
            source_detail=source_detail,
        )
    if "inconclusivo" in lowered or "manual_review" in lowered or "manual review" in lowered:
        return ApplicationOperationalInsight(
            classification="manual_review",
            reason_code="fluxo_inconclusivo",
            summary="fluxo exige revisao manual",
            source_detail=source_detail,
        )
    if "readiness=" in lowered or "bloqueio=" in lowered:
        return ApplicationOperationalInsight(
            classification="blocked",
            reason_code="bloqueio_funcional",
            summary="bloqueio funcional",
            source_detail=source_detail,
        )
    return ApplicationOperationalInsight(
        classification="unknown",
        reason_code="nao_classificado",
        summary="nao classificado",
        source_detail=source_detail,
    )


def classify_application_operational_insight(application: JobApplication) -> ApplicationOperationalInsight:
    if application.status == "submitted":
        return ApplicationOperationalInsight(
            classification="submitted",
            reason_code="submitted",
            summary="submetida",
            source_detail=application.last_submit_detail,
        )

    source_detail = (
        application.last_error
        or application.last_submit_detail
        or application.last_preflight_detail
        or ""
    ).strip()
    return classify_operational_detail(source_detail)


def describe_manual_review_need(application: JobApplication) -> str:
    insight = classify_application_operational_insight(application)
    rationale = (application.support_rationale or "").strip()

    main_reason = rationale or insight.summary or "fluxo exige revisao manual"
    next_step = _next_step_for_manual_review(insight.reason_code)
    return (
        f"revisao_humana=necessaria | "
        f"motivo_principal={main_reason} | "
        f"proximo_passo={next_step}"
    )


def _next_step_for_manual_review(reason_code: str) -> str:
    if reason_code == "perguntas_adicionais":
        return "inspecionar as perguntas pendentes antes de autorizar envio"
    if reason_code == "similar_jobs":
        return "revisar a vaga original; nao autorizar submit a partir desta tela"
    if reason_code == "candidatura_externa":
        return "tratar fora do fluxo assistido do LinkedIn"
    if reason_code == "cta_detectado":
        return "validar manualmente o fluxo antes de autorizar envio"
    if reason_code == "bloqueio_funcional":
        return "verificar o detalhe operacional e decidir se cancela ou reprocessa"
    if reason_code == "fluxo_inconclusivo":
        return "abrir a candidatura e validar manualmente o fluxo"
    return "confirmar manualmente o fluxo antes de autorizar envio"
