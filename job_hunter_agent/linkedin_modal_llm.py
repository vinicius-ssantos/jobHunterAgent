from __future__ import annotations

from dataclasses import dataclass

from job_hunter_agent.browser_support import extract_json_object
from job_hunter_agent.linkedin_application import LinkedInApplicationPageState


@dataclass(frozen=True)
class LinkedInModalInterpretation:
    step_type: str
    recommended_action: str
    confidence: float
    rationale: str


def build_linkedin_modal_snapshot_payload(state: LinkedInApplicationPageState) -> dict:
    return {
        "modal_open": state.modal_open,
        "headings": list(state.modal_headings),
        "buttons": list(state.modal_buttons),
        "fields": list(state.modal_fields),
        "resumable_fields": list(state.resumable_fields),
        "filled_fields": list(state.filled_fields),
        "signals": {
            "next_visible": state.modal_next_visible,
            "review_visible": state.modal_review_visible,
            "submit_visible": state.modal_submit_visible,
            "file_upload": state.modal_file_upload,
            "questions_visible": state.modal_questions_visible,
            "uploaded_resume": state.uploaded_resume,
            "progressed_to_next_step": state.progressed_to_next_step,
            "reached_review_step": state.reached_review_step,
            "ready_to_submit": state.ready_to_submit,
        },
        "sample": state.modal_sample,
    }


def deterministic_interpret_linkedin_modal(state: LinkedInApplicationPageState) -> LinkedInModalInterpretation:
    if not state.modal_open:
        return LinkedInModalInterpretation(
            step_type="closed",
            recommended_action="reopen_modal",
            confidence=1.0,
            rationale="o modal nao esta aberto",
        )
    if state.ready_to_submit or (state.modal_submit_visible and not state.modal_next_visible):
        return LinkedInModalInterpretation(
            step_type="review_final",
            recommended_action="submit_if_authorized",
            confidence=0.95,
            rationale="o botao final de envio esta visivel",
        )
    if state.modal_file_upload and not state.uploaded_resume:
        return LinkedInModalInterpretation(
            step_type="resume_upload",
            recommended_action="upload_resume",
            confidence=0.9,
            rationale="o modal exige upload de curriculo antes de prosseguir",
        )
    if state.modal_review_visible and not state.reached_review_step:
        return LinkedInModalInterpretation(
            step_type="review_transition",
            recommended_action="open_review",
            confidence=0.85,
            rationale="a etapa de revisao esta disponivel e ainda nao foi aberta",
        )
    if state.modal_next_visible:
        return LinkedInModalInterpretation(
            step_type="multi_step_form",
            recommended_action="click_next",
            confidence=0.8,
            rationale="o fluxo ainda possui etapas intermediarias",
        )
    if state.modal_questions_visible:
        return LinkedInModalInterpretation(
            step_type="screening_questions",
            recommended_action="manual_review",
            confidence=0.75,
            rationale="ha perguntas obrigatorias que podem exigir decisao humana",
        )
    return LinkedInModalInterpretation(
        step_type="unknown",
        recommended_action="manual_review",
        confidence=0.6,
        rationale="o estado do modal nao ficou claro o suficiente",
    )


class OllamaLinkedInModalInterpreter:
    def __init__(self, model_name: str, base_url: str) -> None:
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise RuntimeError(
                "Dependencias da interpretacao assistida do modal nao estao instaladas. Rode pip install -r requirements.txt."
            ) from exc
        self._llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.1)

    def interpret(self, state: LinkedInApplicationPageState) -> LinkedInModalInterpretation:
        payload = build_linkedin_modal_snapshot_payload(state)
        response = self._llm.invoke(
            f"""
            Classifique a etapa atual de um modal de candidatura do LinkedIn.

            Regras:
            - Responda apenas JSON.
            - Seja conservador.
            - Nao invente campos nao presentes no snapshot.
            - step_type deve ser um de:
              - closed
              - contact
              - resume_upload
              - multi_step_form
              - review_transition
              - review_final
              - screening_questions
              - unknown
            - recommended_action deve ser um de:
              - reopen_modal
              - fill_contact
              - upload_resume
              - click_next
              - open_review
              - submit_if_authorized
              - manual_review

            Snapshot:
            {payload}

            Retorne apenas JSON:
            {{
              "step_type": "unknown",
              "recommended_action": "manual_review",
              "confidence": 0.0,
              "rationale": "motivo curto em portugues"
            }}
            """
        )
        response_text = response.content if hasattr(response, "content") else str(response)
        return parse_linkedin_modal_interpretation_response(response_text)


def parse_linkedin_modal_interpretation_response(response_text: str) -> LinkedInModalInterpretation:
    payload = extract_json_object(response_text)
    if not payload:
        return LinkedInModalInterpretation(
            step_type="unknown",
            recommended_action="manual_review",
            confidence=0.0,
            rationale="resposta do modelo sem JSON valido",
        )

    step_type = str(payload.get("step_type", "")).strip()
    recommended_action = str(payload.get("recommended_action", "")).strip()
    rationale = str(payload.get("rationale", "")).strip() or "sem justificativa do modelo"
    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    valid_step_types = {
        "closed",
        "contact",
        "resume_upload",
        "multi_step_form",
        "review_transition",
        "review_final",
        "screening_questions",
        "unknown",
    }
    valid_actions = {
        "reopen_modal",
        "fill_contact",
        "upload_resume",
        "click_next",
        "open_review",
        "submit_if_authorized",
        "manual_review",
    }
    if step_type not in valid_step_types or recommended_action not in valid_actions:
        return LinkedInModalInterpretation(
            step_type="unknown",
            recommended_action="manual_review",
            confidence=0.0,
            rationale="modelo retornou classificacao invalida",
        )
    confidence = max(0.0, min(1.0, confidence))
    return LinkedInModalInterpretation(
        step_type=step_type,
        recommended_action=recommended_action,
        confidence=confidence,
        rationale=rationale,
    )


def format_linkedin_modal_interpretation(interpretation: LinkedInModalInterpretation) -> str:
    return (
        "interpretacao_modal="
        f"etapa={interpretation.step_type}; "
        f"acao={interpretation.recommended_action}; "
        f"confianca={interpretation.confidence:.2f}; "
        f"motivo={interpretation.rationale}"
    )
