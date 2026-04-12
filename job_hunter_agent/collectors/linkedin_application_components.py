from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from job_hunter_agent.core.candidate_profile import CandidateProfile
from job_hunter_agent.collectors.linkedin_application_entry_strategies import (
    LinkedInApplyHtmlRecoveryStrategy,
)
from job_hunter_agent.collectors.linkedin_application_modal import LinkedInEasyApplyModalDriver
from job_hunter_agent.collectors.linkedin_application_navigation import LinkedInEasyApplyNavigator
from job_hunter_agent.collectors.linkedin_application_reader import LinkedInApplicationPageReader


class SystemSubmittedAtProvider:
    def __call__(self) -> str:
        return datetime.now().isoformat(timespec="seconds")


@dataclass(frozen=True)
class LinkedInApplicationFlowComponents:
    navigator: LinkedInEasyApplyNavigator
    page_reader: LinkedInApplicationPageReader
    modal_driver: LinkedInEasyApplyModalDriver
    html_recovery: LinkedInApplyHtmlRecoveryStrategy
    submitted_at_provider: Callable[[], str]


def create_linkedin_application_flow_components(
    *,
    resume_path: str | Path | None = None,
    contact_email: str = "",
    phone: str = "",
    phone_country_code: str = "",
    candidate_profile: CandidateProfile | None = None,
    candidate_profile_path: str | Path | None = None,
    modal_interpreter=None,
    submitted_at_provider: Callable[[], str] | None = None,
) -> LinkedInApplicationFlowComponents:
    return LinkedInApplicationFlowComponents(
        navigator=LinkedInEasyApplyNavigator(),
        page_reader=LinkedInApplicationPageReader(),
        modal_driver=LinkedInEasyApplyModalDriver(
            resume_path=Path(resume_path).resolve() if resume_path else None,
            contact_email=contact_email.strip(),
            phone=phone.strip(),
            phone_country_code=phone_country_code.strip(),
            candidate_profile=candidate_profile,
            candidate_profile_path=Path(candidate_profile_path).resolve() if candidate_profile_path else None,
            modal_interpreter=modal_interpreter,
        ),
        html_recovery=LinkedInApplyHtmlRecoveryStrategy(),
        submitted_at_provider=submitted_at_provider or SystemSubmittedAtProvider(),
    )
