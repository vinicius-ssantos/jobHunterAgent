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
class LinkedInApplicationPageSignals:
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
    modal_headings: tuple[str, ...] = ()
    modal_buttons: tuple[str, ...] = ()
    modal_fields: tuple[str, ...] = ()
    modal_questions: tuple[str, ...] = ()


@dataclass(frozen=True)
class LinkedInApplicationOperationalSignals:
    resumable_fields: tuple[str, ...] = ()
    filled_fields: tuple[str, ...] = ()
    progressed_to_next_step: bool = False
    uploaded_resume: bool = False
    reached_review_step: bool = False
    ready_to_submit: bool = False
    answered_questions: tuple[str, ...] = ()
    unanswered_questions: tuple[str, ...] = ()


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

    def page_signals(self) -> LinkedInApplicationPageSignals:
        return LinkedInApplicationPageSignals(
            current_url=self.current_url,
            easy_apply=self.easy_apply,
            external_apply=self.external_apply,
            submit_visible=self.submit_visible,
            modal_open=self.modal_open,
            modal_submit_visible=self.modal_submit_visible,
            modal_next_visible=self.modal_next_visible,
            modal_review_visible=self.modal_review_visible,
            modal_file_upload=self.modal_file_upload,
            modal_questions_visible=self.modal_questions_visible,
            save_application_dialog_visible=self.save_application_dialog_visible,
            cta_text=self.cta_text,
            sample=self.sample,
            modal_sample=self.modal_sample,
            contact_email_visible=self.contact_email_visible,
            contact_phone_visible=self.contact_phone_visible,
            country_code_visible=self.country_code_visible,
            work_authorization_visible=self.work_authorization_visible,
            years_of_experience_visible=self.years_of_experience_visible,
            modal_headings=self.modal_headings,
            modal_buttons=self.modal_buttons,
            modal_fields=self.modal_fields,
            modal_questions=self.modal_questions,
        )

    def operational_signals(self) -> LinkedInApplicationOperationalSignals:
        return LinkedInApplicationOperationalSignals(
            resumable_fields=self.resumable_fields,
            filled_fields=self.filled_fields,
            progressed_to_next_step=self.progressed_to_next_step,
            uploaded_resume=self.uploaded_resume,
            reached_review_step=self.reached_review_step,
            ready_to_submit=self.ready_to_submit,
            answered_questions=self.answered_questions,
            unanswered_questions=self.unanswered_questions,
        )

    def has_pending_questions(self) -> bool:
        return bool(self.operational_signals().unanswered_questions)

    def has_resumable_fields(self) -> bool:
        return bool(self.operational_signals().resumable_fields)

    def has_any_filled_fields(self) -> bool:
        return bool(self.operational_signals().filled_fields)


class LinkedInPreflightClassificationStrategy(Protocol):
    def classify(self, state: "LinkedInApplicationPageState") -> "LinkedInApplicationInspection | None": ...


def build_linkedin_modal_snapshot(state: LinkedInApplicationPageState) -> str:
    page = state.page_signals()
    progress = state.operational_signals()
    parts: list[str] = []
    if page.modal_headings:
        parts.append(f"titulos={', '.join(page.modal_headings[:3])}")
    if page.modal_buttons:
        parts.append(f"botoes={', '.join(page.modal_buttons[:5])}")
    if page.modal_fields:
        parts.append(f"campos_detectados={', '.join(page.modal_fields[:5])}")
    if page.modal_questions:
        parts.append(f"perguntas={', '.join(page.modal_questions[:4])}")
    if progress.answered_questions:
        parts.append(f"respondidas={', '.join(progress.answered_questions[:3])}")
    if progress.unanswered_questions:
        parts.append(f"pendentes={', '.join(progress.unanswered_questions[:3])}")
    if not parts:
        return "snapshot_modal=indisponivel"
    return "snapshot_modal=" + " | ".join(parts)


def describe_linkedin_modal_blocker(state: LinkedInApplicationPageState) -> str:
    page = state.page_signals()
    progress = state.operational_signals()
    blockers: list[str] = []
    if not page.modal_open:
        blockers.append("modal_fechado")
    if page.easy_apply and "/apply/" in page.sample:
        blockers.append("fluxo_apply_sem_modal")
    if page.save_application_dialog_visible:
        blockers.append("confirmacao_salvar_candidatura")
    if page.modal_questions_visible:
        blockers.append("perguntas_obrigatorias")
    if progress.unanswered_questions:
        blockers.append("perguntas_nao_mapeadas")
    if page.modal_file_upload and not progress.uploaded_resume:
        blockers.append("upload_cv_pendente")
    if page.modal_next_visible and not progress.progressed_to_next_step:
        blockers.append("etapa_intermediaria")
    if is_linkedin_review_transition_available(state) and not progress.reached_review_step:
        blockers.append("revisao_nao_alcancada")
    if not page.modal_submit_visible:
        blockers.append("botao_submit_ausente")
    if progress.resumable_fields and not progress.filled_fields:
        blockers.append("campos_nao_preenchidos")
    if not blockers:
        blockers.append("estado_modal_inconclusivo")
    return ", ".join(blockers)


def describe_linkedin_easy_apply_entrypoint(state: LinkedInApplicationPageState) -> str:
    page = state.page_signals()
    parts: list[str] = []
    if page.cta_text:
        parts.append(f"cta={page.cta_text}")
    if page.sample:
        parts.append(f"pagina={page.sample[:180]}")
    if not parts:
        return "entrada_easy_apply=indisponivel"
    return " | ".join(parts)


def describe_linkedin_job_page_readiness(readiness: LinkedInJobPageReadiness) -> str:
    detail = f"readiness={readiness.result} | motivo={readiness.reason}"
    if readiness.sample:
        detail = f"{detail} | pagina={readiness.sample[:180]}"
    return detail


def _build_modal_detail_parts(state: LinkedInApplicationPageState) -> list[str]:
    progress = state.operational_signals()
    detail_parts: list[str] = ["preflight real"]
    if progress.resumable_fields:
        detail_parts.append(f"campos={', '.join(progress.resumable_fields)}")
    if progress.filled_fields:
        detail_parts.append(f"preenchidos={', '.join(progress.filled_fields)}")
    if progress.progressed_to_next_step:
        detail_parts.append("avancou_proxima_etapa=sim")
    if progress.uploaded_resume:
        detail_parts.append("curriculo_carregado=sim")
    if progress.reached_review_step:
        detail_parts.append("revisao_final_alcancada=sim")
    if progress.ready_to_submit:
        detail_parts.append("pronto_para_envio=sim")
    return detail_parts


@dataclass(frozen=True)
class LinkedInModalReadyClassificationStrategy:
    def classify(self, state: LinkedInApplicationPageState) -> LinkedInApplicationInspection | None:
        page = state.page_signals()
        if not page.modal_open:
            return None
        if not DEFAULT_LINKEDIN_REVIEW_FINAL_STRATEGY.is_final_ready(state):
            return None
        detail_parts = _build_modal_detail_parts(state)
        detail_parts.append("ok: fluxo pronto para submissao assistida no LinkedIn")
        if page.cta_text:
            detail_parts.append(f"cta={page.cta_text}")
        if page.modal_sample:
            detail_parts.append(f"modal={page.modal_sample}")
        detail_parts.append(build_linkedin_modal_snapshot(state))
        return LinkedInApplicationInspection(
            outcome="ready",
            detail=" | ".join(detail_parts),
        )


@dataclass(frozen=True)
class LinkedInModalManualReviewClassificationStrategy:
    def classify(self, state: LinkedInApplicationPageState) -> LinkedInApplicationInspection | None:
        page = state.page_signals()
        progress = state.operational_signals()
        if not page.modal_open:
            return None
        detail_parts = _build_modal_detail_parts(state)
        detail_parts.append("inconclusivo: fluxo do LinkedIn exige revisao manual")
        if page.modal_next_visible:
            detail_parts.append("passos_adicionais=sim")
        if is_linkedin_review_transition_available(state):
            detail_parts.append("revisao_final=sim")
        if page.modal_file_upload:
            detail_parts.append("upload_cv=sim")
        if page.modal_questions_visible:
            detail_parts.append("perguntas=sim")
        if progress.answered_questions:
            detail_parts.append(f"perguntas_respondidas={', '.join(progress.answered_questions[:3])}")
        if progress.unanswered_questions:
            detail_parts.append(f"perguntas_pendentes={', '.join(progress.unanswered_questions[:3])}")
        if page.cta_text:
            detail_parts.append(f"cta={page.cta_text}")
        if page.modal_sample:
            detail_parts.append(f"modal={page.modal_sample}")
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
