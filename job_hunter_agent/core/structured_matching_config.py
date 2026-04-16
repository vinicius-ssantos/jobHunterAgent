from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from job_hunter_agent.core.legacy_matching_config import LegacyMatchingConfig
from job_hunter_agent.core.seniority import normalize_seniority_label


@dataclass(frozen=True)
class StructuredCandidateProfile:
    summary: str


@dataclass(frozen=True)
class StructuredMatchingConfig:
    include_keywords: tuple[str, ...]
    exclude_keywords: tuple[str, ...]
    accepted_work_modes: tuple[str, ...]
    minimum_salary_brl: int
    minimum_relevance: int
    target_seniorities: tuple[str, ...] = ()
    allow_unknown_seniority: bool = True


@dataclass(frozen=True)
class StructuredMatchingSource:
    profile: StructuredCandidateProfile
    matching: StructuredMatchingConfig


@dataclass(frozen=True)
class ResolvedStructuredMatchingSource:
    config: StructuredMatchingSource
    source: str
    path: Path | None = None

    @property
    def used_legacy_fallback(self) -> bool:
        return self.source == "legacy_fallback"

    def describe_source(self) -> str:
        if self.source == "structured_file":
            return f"matching estruturado carregado de arquivo: {self.path}"
        if self.source == "legacy_fallback":
            return f"matching estruturado ausente em {self.path}; usando fallback legado"
        return f"matching estruturado resolvido de fonte desconhecida: {self.source}"


def load_structured_matching_source(path: str | Path) -> StructuredMatchingSource:
    config_path = Path(path)
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Arquivo de matching estruturado nao encontrado: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Arquivo de matching estruturado invalido: JSON malformado em {config_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Arquivo de matching estruturado invalido: raiz deve ser um objeto JSON.")
    return parse_structured_matching_source(payload)


def parse_structured_matching_source(payload: dict[str, Any]) -> StructuredMatchingSource:
    profile_payload = _require_dict(payload, "profile")
    matching_payload = _require_dict(payload, "matching")
    return StructuredMatchingSource(
        profile=StructuredCandidateProfile(
            summary=_require_non_empty_string(profile_payload, "summary", section="profile"),
        ),
        matching=StructuredMatchingConfig(
            include_keywords=_require_string_list(matching_payload, "include_keywords", section="matching"),
            exclude_keywords=_optional_string_list(matching_payload, "exclude_keywords"),
            accepted_work_modes=_optional_string_list(matching_payload, "accepted_work_modes"),
            minimum_salary_brl=_require_non_negative_int(
                matching_payload,
                "minimum_salary_brl",
                section="matching",
            ),
            minimum_relevance=_require_int_in_range(
                matching_payload,
                "minimum_relevance",
                section="matching",
                minimum=1,
                maximum=10,
            ),
            target_seniorities=_optional_seniority_list(matching_payload, "target_seniorities"),
            allow_unknown_seniority=_optional_bool(
                matching_payload,
                "allow_unknown_seniority",
                default=True,
                section="matching",
            ),
        ),
    )


def build_structured_matching_source_from_legacy(
    legacy_matching: LegacyMatchingConfig,
) -> StructuredMatchingSource:
    from job_hunter_agent.core.seniority import infer_seniority_from_text

    inferred = infer_seniority_from_text(legacy_matching.profile_text)
    target_seniorities = () if inferred == "nao_informada" else (inferred,)
    return StructuredMatchingSource(
        profile=StructuredCandidateProfile(summary=legacy_matching.profile_text),
        matching=StructuredMatchingConfig(
            include_keywords=legacy_matching.include_keywords,
            exclude_keywords=legacy_matching.exclude_keywords,
            accepted_work_modes=legacy_matching.accepted_work_modes,
            minimum_salary_brl=legacy_matching.minimum_salary_brl,
            minimum_relevance=legacy_matching.minimum_relevance,
            target_seniorities=target_seniorities,
            allow_unknown_seniority=True,
        ),
    )


def resolve_structured_matching_source(
    *,
    structured_matching_config_path: str | Path,
    legacy_matching: LegacyMatchingConfig,
    legacy_fallback_enabled: bool,
) -> ResolvedStructuredMatchingSource:
    config_path = Path(structured_matching_config_path)
    if config_path.exists():
        return ResolvedStructuredMatchingSource(
            config=load_structured_matching_source(config_path),
            source="structured_file",
            path=config_path,
        )
    if not legacy_fallback_enabled:
        raise ValueError(
            f"Arquivo de matching estruturado nao encontrado em {config_path} e o fallback legado esta desabilitado."
        )
    return ResolvedStructuredMatchingSource(
        config=build_structured_matching_source_from_legacy(legacy_matching),
        source="legacy_fallback",
        path=config_path,
    )


def _require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Arquivo de matching estruturado invalido: secao '{key}' ausente ou invalida.")
    return value


def _require_non_empty_string(payload: dict[str, Any], key: str, *, section: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Arquivo de matching estruturado invalido: campo '{section}.{key}' deve ser texto nao vazio."
        )
    return value.strip()


def _require_string_list(payload: dict[str, Any], key: str, *, section: str) -> tuple[str, ...]:
    values = _optional_string_list(payload, key)
    if not values:
        raise ValueError(
            f"Arquivo de matching estruturado invalido: campo '{section}.{key}' deve conter ao menos um item."
        )
    return values


def _optional_string_list(payload: dict[str, Any], key: str) -> tuple[str, ...]:
    raw_value = payload.get(key, [])
    if raw_value is None:
        return ()
    if not isinstance(raw_value, list):
        raise ValueError(f"Arquivo de matching estruturado invalido: campo '{key}' deve ser lista.")
    normalized: list[str] = []
    for item in raw_value:
        if not isinstance(item, str):
            raise ValueError("Arquivo de matching estruturado invalido: listas devem conter apenas strings.")
        token = item.strip().lower()
        if token and token not in normalized:
            normalized.append(token)
    return tuple(normalized)


def _optional_seniority_list(payload: dict[str, Any], key: str) -> tuple[str, ...]:
    raw_values = _optional_string_list(payload, key)
    normalized: list[str] = []
    for value in raw_values:
        token = normalize_seniority_label(value)
        if token == "nao_informada":
            raise ValueError(
                f"Arquivo de matching estruturado invalido: campo '{key}' contem senioridade invalida: {value}."
            )
        if token not in normalized:
            normalized.append(token)
    return tuple(normalized)


def _require_non_negative_int(payload: dict[str, Any], key: str, *, section: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or value < 0:
        raise ValueError(
            f"Arquivo de matching estruturado invalido: campo '{section}.{key}' deve ser inteiro >= 0."
        )
    return value


def _require_int_in_range(
    payload: dict[str, Any],
    key: str,
    *,
    section: str,
    minimum: int,
    maximum: int,
) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or not (minimum <= value <= maximum):
        raise ValueError(
            f"Arquivo de matching estruturado invalido: campo '{section}.{key}' deve estar entre {minimum} e {maximum}."
        )
    return value


def _optional_bool(payload: dict[str, Any], key: str, *, default: bool, section: str) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(
            f"Arquivo de matching estruturado invalido: campo '{section}.{key}' deve ser booleano."
        )
    return value
