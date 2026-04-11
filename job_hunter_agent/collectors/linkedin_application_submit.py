from __future__ import annotations

from dataclasses import dataclass

from job_hunter_agent.collectors.linkedin_application_state import (
    LinkedInApplicationPageState,
    build_linkedin_modal_snapshot,
    describe_linkedin_easy_apply_entrypoint,
    describe_linkedin_modal_blocker,
)


@dataclass(frozen=True)
class LinkedInSubmitReadinessDecision:
    ready: bool
    detail: str


def evaluate_linkedin_submit_readiness(
    state: LinkedInApplicationPageState,
    *,
    interpretation_detail: str = "",
) -> LinkedInSubmitReadinessDecision:
    if state.modal_open and state.modal_submit_visible:
        return LinkedInSubmitReadinessDecision(ready=True, detail="")

    snapshot_detail = f" | {build_linkedin_modal_snapshot(state)}" if state.modal_open else ""
    detail = (
        "submissao real bloqueada: fluxo nao chegou ao botao de envio"
        f" | bloqueio={describe_linkedin_modal_blocker(state)}"
        f" | modal={state.modal_sample or 'nao_informado'}"
        f" | {describe_linkedin_easy_apply_entrypoint(state)}"
        f"{interpretation_detail}"
        f"{snapshot_detail}"
    )
    return LinkedInSubmitReadinessDecision(ready=False, detail=detail)
