from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from job_hunter_agent.core.domain import JobPosting
from job_hunter_agent.core.portal_capabilities import get_portal_capabilities


@dataclass(frozen=True)
class ApplicationExecutionReadiness:
    ok: bool
    failures: tuple[str, ...]
    warnings: tuple[str, ...] = ()


class ApplicationReadinessCheckService:
    def __init__(
        self,
        *,
        linkedin_storage_state_path: str | Path,
        resume_path: str | Path,
        contact_email: str,
        phone: str,
        phone_country_code: str,
    ) -> None:
        self.linkedin_storage_state_path = Path(linkedin_storage_state_path).resolve()
        self.resume_path = Path(resume_path).resolve()
        self.contact_email = contact_email.strip()
        self.phone = phone.strip()
        self.phone_country_code = phone_country_code.strip()

    def check_submit_ready(self, job: JobPosting) -> ApplicationExecutionReadiness:
        capabilities = get_portal_capabilities(job)
        failures: list[str] = []

        if not capabilities.submit_supported:
            failures.append(f"portal {capabilities.portal_name} ainda nao suporta submit real")
            return ApplicationExecutionReadiness(ok=False, failures=tuple(failures))

        if capabilities.requires_login and not self.linkedin_storage_state_path.exists():
            failures.append("sessao autenticada do LinkedIn nao encontrada")
        if not self.resume_path.exists():
            failures.append("curriculo configurado nao foi encontrado")
        if not self.contact_email:
            failures.append("email de contato nao configurado")
        if not self.phone:
            failures.append("telefone de contato nao configurado")
        if not self.phone_country_code:
            failures.append("codigo do pais do telefone nao configurado")

        return ApplicationExecutionReadiness(ok=not failures, failures=tuple(failures))
