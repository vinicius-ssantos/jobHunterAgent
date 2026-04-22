from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LinkedInCompanyPolicy:
    trailing_location_fragments: tuple[str, ...]
    standalone_location_tokens: tuple[str, ...]
    noise_phrases: tuple[str, ...]
    work_mode_tokens: tuple[str, ...]

    @property
    def trailing_location_set(self) -> set[str]:
        return set(self.trailing_location_fragments)

    @property
    def standalone_location_set(self) -> set[str]:
        return set(self.standalone_location_tokens)

    @property
    def work_mode_set(self) -> set[str]:
        return set(self.work_mode_tokens)


_runtime_linkedin_company_policy_path = Path("./linkedin_company_policy.json")
_cached_runtime_policy: LinkedInCompanyPolicy | None = None
_cached_runtime_policy_path: Path | None = None


def set_runtime_linkedin_company_policy_path(path: str | Path) -> None:
    global _runtime_linkedin_company_policy_path, _cached_runtime_policy, _cached_runtime_policy_path
    _runtime_linkedin_company_policy_path = Path(path)
    _cached_runtime_policy = None
    _cached_runtime_policy_path = None


def get_runtime_linkedin_company_policy() -> LinkedInCompanyPolicy:
    global _cached_runtime_policy, _cached_runtime_policy_path
    runtime_path = _runtime_linkedin_company_policy_path.resolve()
    if _cached_runtime_policy is not None and _cached_runtime_policy_path == runtime_path:
        return _cached_runtime_policy
    loaded = load_linkedin_company_policy(runtime_path)
    _cached_runtime_policy = loaded
    _cached_runtime_policy_path = runtime_path
    return loaded


def load_linkedin_company_policy(path: str | Path) -> LinkedInCompanyPolicy:
    policy_path = Path(path)
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Arquivo de politica de company do LinkedIn nao encontrado: {policy_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Arquivo de politica de company do LinkedIn invalido: JSON malformado em {policy_path}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("Arquivo de politica de company do LinkedIn invalido: raiz deve ser um objeto JSON.")
    return parse_linkedin_company_policy(payload)


def parse_linkedin_company_policy(payload: dict[str, Any]) -> LinkedInCompanyPolicy:
    return LinkedInCompanyPolicy(
        trailing_location_fragments=_required_string_list(payload, "trailing_location_fragments"),
        standalone_location_tokens=_required_string_list(payload, "standalone_location_tokens"),
        noise_phrases=_required_string_list(payload, "noise_phrases"),
        work_mode_tokens=_required_string_list(payload, "work_mode_tokens"),
    )


def _required_string_list(payload: dict[str, Any], key: str) -> tuple[str, ...]:
    raw = payload.get(key)
    if not isinstance(raw, list):
        raise ValueError(f"Arquivo de politica de company do LinkedIn invalido: campo '{key}' deve ser lista.")
    normalized: list[str] = []
    for item in raw:
        token = str(item).strip().lower()
        if token and token not in normalized:
            normalized.append(token)
    if not normalized:
        raise ValueError(
            f"Arquivo de politica de company do LinkedIn invalido: campo '{key}' deve conter ao menos um item."
        )
    return tuple(normalized)
