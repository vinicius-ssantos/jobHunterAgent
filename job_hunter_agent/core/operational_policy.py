from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OperationalPolicy:
    operational_summary_order: tuple[str, ...]
    queue_reason_rank: dict[str, int]
    queue_unknown_reason_rank: int
    queue_auto_supported_unknown_rank: int
    queue_cta_unknown_rank: int
    support_order: dict[str, int]
    priority_order: dict[str, int]


_runtime_operational_policy_path = Path("./operational_policy.json")
_cached_runtime_policy: OperationalPolicy | None = None
_cached_runtime_policy_path: Path | None = None


def set_runtime_operational_policy_path(path: str | Path) -> None:
    global _runtime_operational_policy_path, _cached_runtime_policy, _cached_runtime_policy_path
    _runtime_operational_policy_path = Path(path)
    _cached_runtime_policy = None
    _cached_runtime_policy_path = None


def get_runtime_operational_policy() -> OperationalPolicy:
    global _cached_runtime_policy, _cached_runtime_policy_path
    runtime_path = _runtime_operational_policy_path.resolve()
    if _cached_runtime_policy is not None and _cached_runtime_policy_path == runtime_path:
        return _cached_runtime_policy
    loaded = load_operational_policy(runtime_path)
    _cached_runtime_policy = loaded
    _cached_runtime_policy_path = runtime_path
    return loaded


def load_operational_policy(path: str | Path) -> OperationalPolicy:
    policy_path = Path(path)
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Arquivo de politica operacional nao encontrado: {policy_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Arquivo de politica operacional invalido: JSON malformado em {policy_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Arquivo de politica operacional invalido: raiz deve ser um objeto JSON.")
    return parse_operational_policy(payload)


def parse_operational_policy(payload: dict[str, Any]) -> OperationalPolicy:
    return OperationalPolicy(
        operational_summary_order=_required_string_list(payload, "operational_summary_order"),
        queue_reason_rank=_required_int_map(payload, "queue_reason_rank"),
        queue_unknown_reason_rank=_required_non_negative_int(payload, "queue_unknown_reason_rank"),
        queue_auto_supported_unknown_rank=_required_non_negative_int(payload, "queue_auto_supported_unknown_rank"),
        queue_cta_unknown_rank=_required_non_negative_int(payload, "queue_cta_unknown_rank"),
        support_order=_required_int_map(payload, "support_order"),
        priority_order=_required_int_map(payload, "priority_order"),
    )


def _required_string_list(payload: dict[str, Any], key: str) -> tuple[str, ...]:
    raw = payload.get(key)
    if not isinstance(raw, list):
        raise ValueError(f"Arquivo de politica operacional invalido: campo '{key}' deve ser lista.")
    normalized: list[str] = []
    for item in raw:
        token = str(item).strip()
        if token and token not in normalized:
            normalized.append(token)
    if not normalized:
        raise ValueError(
            f"Arquivo de politica operacional invalido: campo '{key}' deve conter ao menos um item."
        )
    return tuple(normalized)


def _required_int_map(payload: dict[str, Any], key: str) -> dict[str, int]:
    raw = payload.get(key)
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"Arquivo de politica operacional invalido: campo '{key}' ausente ou invalido.")
    normalized: dict[str, int] = {}
    for raw_key, raw_value in raw.items():
        token = str(raw_key).strip()
        if not token:
            continue
        if not isinstance(raw_value, int) or raw_value < 0:
            raise ValueError(
                f"Arquivo de politica operacional invalido: campo '{key}.{raw_key}' deve ser inteiro >= 0."
            )
        normalized[token] = raw_value
    if not normalized:
        raise ValueError(f"Arquivo de politica operacional invalido: campo '{key}' sem entradas validas.")
    return normalized


def _required_non_negative_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"Arquivo de politica operacional invalido: campo '{key}' deve ser inteiro >= 0.")
    return value
