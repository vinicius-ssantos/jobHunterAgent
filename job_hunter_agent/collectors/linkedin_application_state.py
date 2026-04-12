from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from job_hunter_agent.collectors.linkedin_application_review import (
    DEFAULT_LINKEDIN_REVIEW_FINAL_STRATEGY,
    is_linkedin_review_final_ready,
    is_linkedin_review_transition_available,
)


@dataclass(frozen=True)
class LinkedInApplicationInspection:
    outcome: str
    detail: str


@dataclass(frozen=True)
class LinkedInJobPageReadiness:
    result: str
    reason: str
    sample: str


@dataclass(frozen=True)
class LinkedInApplicationPageState:
    current_url: str = ""
    easy_apply: bool = False
    external_apply: bool = False
    submit_visible: bool = False
    modal_open: bool = False
    modal_submit_visible: bool = False
    modal_next_visible: bool = False
    modal_review_visible: bool = False
    modal_file_upload: bool = False
    modal_questions_visible: bool = False
    save_application_dialog_visible: bool = False
    cta_text: str = ""
    sample: str = ""
    modal_sample: str = ""
    contact_email_visible: bool = False
    contact_phone_visible: bool = False
    country_code_visible: bool = False
    work_authorization_visible: bool = False
    years_of_experience_visible: bool = False
    resumable_fields: tuple[str, ...] = ()
    filled_fields: tuple[str, ...] = ()
    progressed_to_next_step: bool = False
    uploaded_resume: bool = False
    reached_review_step: bool = False
    ready_to_submit: bool = False
    modal_headings: tuple[str, ...] = ()
    modal_buttons: tuple[str, ...] = ()
    modal_fields: tuple[str, ...] = ()
    modal_questions: tuple[str, ...] = ()
    answered_questions: tuple[str, ...] = ()
    unanswered_questions: tuple[str, ...] = ()


class LinkedInPreflightClassificationStrategy(Protocol):
    def classify(self, state: "LinkedInApplicationPageState") -> "LinkedInApplicationInspection | None": ...


def build_linkedin_modal_snapshot(state: LinkedInApplicationPageState) -> str:
    parts: list[str] = []
    if state.modal_headings:
        parts.append(f"titulos={', '.join(state.modal_headings[:3])}")
    if state.modal_buttons:
        parts.append(f"botoes={', '.join(state.modal_buttons[:5])}")
    if state.modal_fields:
        parts.append(f"campos_detectados={', '.join(state.modal_fields[:5])}")
    if state.modal_questions:
        parts.append(f"perguntas={', '.join(state.modal_questions[:4])}")
    if state.answered_questions:
        parts.append(f"respondidas={', '.join(state.answered_questions[:3])}")
    if state.unanswered_questions:
        parts.append(f"pendentes={', '.join(state.unanswered_questions[:3])}")
    if not parts:
        return "snapshot_modal=indisponivel"
    return "snapshot_modal=" + " | ".join(parts)


def describe_linkedin_modal_blocker(state: LinkedInApplicationPageState) -> str:
    blockers: list[str] = []
    if not state.modal_open:
        blockers.append("modal_fechado")
    if state.easy_apply and "/apply/" in state.sample:
        blockers.append("fluxo_apply_sem_modal")
    if state.save_application_dialog_visible:
        blockers.append("confirmacao_salvar_candidatura")
    if state.modal_questions_visible:
        blockers.append("perguntas_obrigatorias")
    if state.unanswered_questions:
        blockers.append("perguntas_nao_mapeadas")
    if state.modal_file_upload and not state.uploaded_resume:
        blockers.append("upload_cv_pendente")
    if state.modal_next_visible and not state.progressed_to_next_step:
        blockers.append("etapa_intermediaria")
    if is_linkedin_review_transition_available(state) and not state.reached_review_step:
        blockers.append("revisao_nao_alcancada")
    if not state.modal_submit_visible:
        blockers.append("botao_submit_ausente")
    if state.resumable_fields and not state.filled_fields:
        blockers.append("campos_nao_preenchidos")
    if not blockers:
        blockers.append("estado_modal_inconclusivo")
    return ", ".join(blockers)


def describe_linkedin_easy_apply_entrypoint(state: LinkedInApplicationPageState) -> str:
    parts: list[str] = []
    if state.cta_text:
        parts.append(f"cta={state.cta_text}")
    if state.sample:
        parts.append(f"pagina={state.sample[:180]}")
    if not parts:
        return "entrada_easy_apply=indisponivel"
    return " | ".join(parts)


def describe_linkedin_job_page_readiness(readiness: LinkedInJobPageReadiness) -> str:
    detail = f"readiness={readiness.result} | motivo={readiness.reason}"
    if readiness.sample:
        detail = f"{detail} | pagina={readiness.sample[:180]}"
    return detail


def _build_modal_detail_parts(state: LinkedInApplicationPageState) -> list[str]:
    detail_parts: list[str] = ["preflight real"]
    if state.resumable_fields:
        detail_parts.append(f"campos={', '.join(state.resumable_fields)}")
    if state.filled_fields:
        detail_parts.append(f"preenchidos={', '.join(state.filled_fields)}")
    if state.progressed_to_next_step:
        detail_parts.append("avancou_proxima_etapa=sim")
    if state.uploaded_resume:
        detail_parts.append("curriculo_carregado=sim")
    if state.reached_review_step:
        detail_parts.append("revisao_final_alcancada=sim")
    if state.ready_to_submit:
        detail_parts.append("pronto_para_envio=sim")
    return detail_parts


@dataclass(frozen=True)
class LinkedInModalReadyClassificationStrategy:
    def classify(self, state: LinkedInApplicationPageState) -> LinkedInApplicationInspection | None:
        if not state.modal_open:
            return None
        if not DEFAULT_LINKEDIN_REVIEW_FINAL_STRATEGY.is_final_ready(state):
            return None
        detail_parts = _build_modal_detail_parts(state)
        detail_parts.append("ok: fluxo pronto para submissao assistida no LinkedIn")
        if state.cta_text:
            detail_parts.append(f"cta={state.cta_text}")
        if state.modal_sample:
            detail_parts.append(f"modal={state.modal_sample}")
        detail_parts.append(build_linkedin_modal_snapshot(state))
        return LinkedInApplicationInspection(
            outcome="ready",
            detail=" | ".join(detail_parts),
        )


@dataclass(frozen=True)
class LinkedInModalManualReviewClassificationStrategy:
    def classify(self, state: LinkedInApplicationPageState) -> LinkedInApplicationInspection | None:
        if not state.modal_open:
            return None
        detail_parts = _build_modal_detail_parts(state)
        detail_parts.append("inconclusivo: fluxo do LinkedIn exige revisao manual")
        if state.modal_next_visible:
            detail_parts.append("passos_adicionais=sim")
        if is_linkedin_review_transition_available(state):
            detail_parts.append("revisao_final=sim")
        if state.modal_file_upload:
            detail_parts.append("upload_cv=sim")
        if state.modal_questions_visible:
            detail_parts.append("perguntas=sim")
        if state.answered_questions:
            detail_parts.append(f"perguntas_respondidas={', '.join(state.answered_questions[:3])}")
        if state.unanswered_questions:
            detail_parts.append(f"perguntas_pendentes={', '.join(state.unanswered_questions[:3])}")
        if state.cta_text:
            detail_parts.append(f"cta={state.cta_text}")
        if state.modal_sample:
            detail_parts.append(f"modal={state.modal_sample}")
        detail_parts.append(build_linkedin_modal_snapshot(state))
        return LinkedInApplicationInspection(
            outcome="manual_review",
            detail=" | ".join(detail_parts),
        )


@dataclass(frozen=True)
class LinkedInEasyApplyWithoutModalClassificationStrategy:
    def classify(self, state: LinkedInApplicationPageState) -> LinkedInApplicationInspection | None:
        if not state.easy_apply or state.modal_open:
            return None
        return LinkedInApplicationInspection(
            outcome="manual_review",
            detail=(
                "preflight real inconclusivo: CTA de candidatura simplificada encontrado, mas modal nao abriu"
                f" | {describe_linkedin_easy_apply_entrypoint(state)}"
            ),
        )


@dataclass(frozen=True)
class LinkedInExternalApplyClassificationStrategy:
    def classify(self, state: LinkedInApplicationPageState) -> LinkedInApplicationInspection | None:
        if not state.external_apply:
            return None
        return LinkedInApplicationInspection(
            outcome="blocked",
            detail="preflight real bloqueado: vaga redireciona para candidatura externa",
        )


@dataclass(frozen=True)
class LinkedInSubmitVisibleManualReviewClassificationStrategy:
    def classify(self, state: LinkedInApplicationPageState) -> LinkedInApplicationInspection | None:
        if not state.submit_visible:
            return None
        return LinkedInApplicationInspection(
            outcome="manual_review",
            detail="preflight real inconclusivo: pagina interna com CTA de envio sem fluxo simples claro",
        )


@dataclass(frozen=True)
class LinkedInMissingCtaClassificationStrategy:
    def classify(self, state: LinkedInApplicationPageState) -> LinkedInApplicationInspection | None:
        return LinkedInApplicationInspection(
            outcome="blocked",
            detail="preflight real bloqueado: CTA de candidatura nao encontrado na pagina do LinkedIn",
        )


DEFAULT_LINKEDIN_PREFLIGHT_CLASSIFICATION_STRATEGIES: tuple[LinkedInPreflightClassificationStrategy, ...] = (
    LinkedInModalReadyClassificationStrategy(),
    LinkedInModalManualReviewClassificationStrategy(),
    LinkedInEasyApplyWithoutModalClassificationStrategy(),
    LinkedInExternalApplyClassificationStrategy(),
    LinkedInSubmitVisibleManualReviewClassificationStrategy(),
    LinkedInMissingCtaClassificationStrategy(),
)


def classify_linkedin_application_page_state(state: LinkedInApplicationPageState) -> LinkedInApplicationInspection:
    for strategy in DEFAULT_LINKEDIN_PREFLIGHT_CLASSIFICATION_STRATEGIES:
        inspection = strategy.classify(state)
        if inspection is not None:
            return inspection
    return LinkedInApplicationInspection(
        outcome="blocked",
        detail="preflight real bloqueado: classificacao do fluxo indisponivel",
    )
