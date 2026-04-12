from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from job_hunter_agent.core.browser_support import resolve_local_chromium


@dataclass(frozen=True)
class HealthCheckItem:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class ApplicationHealthReport:
    ok: bool
    items: tuple[HealthCheckItem, ...]


def build_application_health_report(settings) -> ApplicationHealthReport:
    items = (
        _check_database_path(settings.database_path),
        _check_linkedin_session(settings.linkedin_storage_state_path),
        _check_resume(settings.resume_path),
        _check_contact_email(settings.application_contact_email),
        _check_contact_phone(settings.application_phone),
        _check_contact_phone_country_code(settings.application_phone_country_code),
        _check_local_chromium(),
        _check_telegram(settings.telegram_token, settings.telegram_chat_id),
        _check_ollama(settings.ollama_model, settings.ollama_url),
    )
    return ApplicationHealthReport(
        ok=all(item.status != "fail" for item in items),
        items=items,
    )


def render_application_health_report(report: ApplicationHealthReport) -> str:
    overall = "ok" if report.ok else "fail"
    lines = [f"Health operacional: {overall}"]
    for item in report.items:
        lines.append(f"- {item.name}={item.status} | {item.detail}")
    return "\n".join(lines)


def _check_database_path(path: str | Path) -> HealthCheckItem:
    database_path = Path(path).resolve()
    if database_path.exists() and database_path.is_dir():
        return HealthCheckItem("database", "fail", f"caminho do banco aponta para diretorio ({database_path})")
    parent = database_path.parent
    if not parent.exists():
        return HealthCheckItem("database", "fail", f"diretorio do banco nao existe ({parent})")
    if not parent.is_dir():
        return HealthCheckItem("database", "fail", f"pai do banco nao e diretorio ({parent})")
    return HealthCheckItem("database", "ok", f"sqlite pronto em {database_path}")


def _check_linkedin_session(path: str | Path) -> HealthCheckItem:
    storage_state_path = Path(path).resolve()
    if not storage_state_path.exists():
        return HealthCheckItem(
            "linkedin_session",
            "fail",
            f"storage_state nao encontrado ({storage_state_path}) | rode --bootstrap-linkedin-session",
        )
    if not storage_state_path.is_file():
        return HealthCheckItem("linkedin_session", "fail", f"storage_state precisa ser arquivo ({storage_state_path})")
    return HealthCheckItem("linkedin_session", "ok", f"storage_state encontrado em {storage_state_path}")


def _check_resume(path: str | Path) -> HealthCheckItem:
    resume_path = Path(path).resolve()
    if not resume_path.exists():
        return HealthCheckItem("resume", "fail", f"curriculo nao encontrado ({resume_path})")
    if not resume_path.is_file():
        return HealthCheckItem("resume", "fail", f"curriculo precisa ser arquivo ({resume_path})")
    return HealthCheckItem("resume", "ok", f"curriculo encontrado em {resume_path}")


def _check_contact_email(value: str) -> HealthCheckItem:
    normalized = value.strip()
    if not normalized:
        return HealthCheckItem("contact_email", "fail", "email de contato nao configurado")
    if "@" not in normalized or "." not in normalized.split("@")[-1]:
        return HealthCheckItem("contact_email", "fail", "email de contato invalido")
    return HealthCheckItem("contact_email", "ok", f"email configurado: {normalized}")


def _check_contact_phone(value: str) -> HealthCheckItem:
    normalized = value.strip()
    digits = "".join(char for char in normalized if char.isdigit())
    if not normalized:
        return HealthCheckItem("contact_phone", "fail", "telefone de contato nao configurado")
    if len(digits) < 8:
        return HealthCheckItem("contact_phone", "fail", "telefone de contato invalido")
    return HealthCheckItem("contact_phone", "ok", f"telefone configurado com {len(digits)} digitos")


def _check_contact_phone_country_code(value: str) -> HealthCheckItem:
    normalized = value.strip()
    digits = "".join(char for char in normalized if char.isdigit())
    if not normalized:
        return HealthCheckItem("phone_country_code", "fail", "codigo do pais nao configurado")
    if not digits:
        return HealthCheckItem("phone_country_code", "fail", "codigo do pais invalido")
    return HealthCheckItem("phone_country_code", "ok", f"codigo do pais configurado: {normalized}")


def _check_local_chromium() -> HealthCheckItem:
    try:
        chromium_path = resolve_local_chromium()
    except Exception as exc:
        return HealthCheckItem("playwright_chromium", "fail", str(exc))
    return HealthCheckItem("playwright_chromium", "ok", f"chromium localizado em {chromium_path}")


def _check_telegram(token: str, chat_id: str) -> HealthCheckItem:
    normalized_token = token.strip()
    normalized_chat_id = chat_id.strip()
    placeholders = {"SEU_TOKEN_AQUI", "SEU_CHAT_ID_AQUI"}
    if not normalized_token or not normalized_chat_id or normalized_token in placeholders or normalized_chat_id in placeholders:
        return HealthCheckItem("telegram", "warn", "telegram opcional nao configurado completamente")
    return HealthCheckItem("telegram", "ok", "telegram configurado")


def _check_ollama(model_name: str, base_url: str) -> HealthCheckItem:
    normalized_model = model_name.strip()
    normalized_url = base_url.strip()
    if not normalized_model:
        return HealthCheckItem("ollama", "warn", "modelo do Ollama nao configurado")
    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return HealthCheckItem("ollama", "warn", "URL do Ollama parece invalida")
    return HealthCheckItem("ollama", "ok", f"ollama configurado: modelo={normalized_model} url={normalized_url}")
