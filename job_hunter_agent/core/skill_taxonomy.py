from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SkillTaxonomy:
    skill_aliases: dict[str, tuple[str, ...]]
    primary_stack_keywords: tuple[str, ...]
    secondary_stack_keywords: tuple[str, ...]
    leadership_keywords: tuple[str, ...]

    @property
    def prompt_focus_stacks(self) -> tuple[str, ...]:
        ordered: list[str] = []
        for token in self.primary_stack_keywords + self.secondary_stack_keywords:
            if token not in ordered:
                ordered.append(token)
        return tuple(ordered)


_runtime_skill_taxonomy_path = Path("./skill_taxonomy.json")
_cached_runtime_taxonomy: SkillTaxonomy | None = None
_cached_runtime_taxonomy_path: Path | None = None


def set_runtime_skill_taxonomy_path(path: str | Path) -> None:
    global _runtime_skill_taxonomy_path, _cached_runtime_taxonomy, _cached_runtime_taxonomy_path
    _runtime_skill_taxonomy_path = Path(path)
    _cached_runtime_taxonomy = None
    _cached_runtime_taxonomy_path = None


def get_runtime_skill_taxonomy() -> SkillTaxonomy:
    global _cached_runtime_taxonomy, _cached_runtime_taxonomy_path
    runtime_path = _runtime_skill_taxonomy_path.resolve()
    if _cached_runtime_taxonomy is not None and _cached_runtime_taxonomy_path == runtime_path:
        return _cached_runtime_taxonomy
    loaded = load_skill_taxonomy(runtime_path)
    _cached_runtime_taxonomy = loaded
    _cached_runtime_taxonomy_path = runtime_path
    return loaded


def load_skill_taxonomy(path: str | Path) -> SkillTaxonomy:
    taxonomy_path = Path(path)
    try:
        payload = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Arquivo de taxonomia de skills nao encontrado: {taxonomy_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Arquivo de taxonomia de skills invalido: JSON malformado em {taxonomy_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Arquivo de taxonomia de skills invalido: raiz deve ser um objeto JSON.")
    return parse_skill_taxonomy(payload)


def parse_skill_taxonomy(payload: dict[str, Any]) -> SkillTaxonomy:
    aliases_payload = payload.get("skill_aliases")
    if not isinstance(aliases_payload, dict) or not aliases_payload:
        raise ValueError("Arquivo de taxonomia de skills invalido: campo 'skill_aliases' ausente ou invalido.")
    skill_aliases: dict[str, tuple[str, ...]] = {}
    for raw_key, raw_value in aliases_payload.items():
        key = str(raw_key).strip().lower()
        if not key:
            continue
        aliases = _normalize_string_list(raw_value, field="skill_aliases")
        merged: list[str] = []
        for token in (key, *aliases):
            if token not in merged:
                merged.append(token)
        skill_aliases[key] = tuple(merged)
    if not skill_aliases:
        raise ValueError("Arquivo de taxonomia de skills invalido: nenhuma skill valida em 'skill_aliases'.")

    return SkillTaxonomy(
        skill_aliases=skill_aliases,
        primary_stack_keywords=_required_string_list(payload, "primary_stack_keywords"),
        secondary_stack_keywords=_required_string_list(payload, "secondary_stack_keywords"),
        leadership_keywords=_required_string_list(payload, "leadership_keywords"),
    )


def _required_string_list(payload: dict[str, Any], key: str) -> tuple[str, ...]:
    values = _normalize_string_list(payload.get(key), field=key)
    if not values:
        raise ValueError(
            f"Arquivo de taxonomia de skills invalido: campo '{key}' deve conter ao menos um item."
        )
    return values


def _normalize_string_list(value: Any, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"Arquivo de taxonomia de skills invalido: campo '{field}' deve ser lista.")
    normalized: list[str] = []
    for item in value:
        token = str(item).strip().lower()
        if token and token not in normalized:
            normalized.append(token)
    return tuple(normalized)
