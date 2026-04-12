from __future__ import annotations

import re

_CANONICAL_SENIORITIES = {
    "junior",
    "pleno",
    "senior",
    "especialista",
    "lideranca",
    "nao_informada",
}

_ALIAS_MAP = {
    "jr": "junior",
    "junior": "junior",
    "júnior": "junior",
    "mid": "pleno",
    "mid-level": "pleno",
    "mid level": "pleno",
    "pleno": "pleno",
    "sr": "senior",
    "senior": "senior",
    "sênior": "senior",
    "staff": "especialista",
    "principal": "especialista",
    "specialist": "especialista",
    "especialista": "especialista",
    "lead": "lideranca",
    "tech lead": "lideranca",
    "team lead": "lideranca",
    "head": "lideranca",
    "coordenador": "lideranca",
    "coordenadora": "lideranca",
    "coord": "lideranca",
    "lideranca": "lideranca",
    "liderança": "lideranca",
    "nao_informada": "nao_informada",
    "não informada": "nao_informada",
}


def normalize_seniority_label(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        return "nao_informada"
    return _ALIAS_MAP.get(normalized, "nao_informada")


def infer_seniority_from_text(text: str) -> str:
    normalized = text.lower()
    checks: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "lideranca",
            (
                "tech lead",
                "team lead",
                "engineering manager",
                "people manager",
                " head ",
                "head of",
                "lideranca",
                "liderança",
                "liderar",
                "coordenador",
                "coordenadora",
                "coord.",
                " coord ",
            ),
        ),
        (
            "especialista",
            (
                "staff",
                "principal",
                "specialist",
                "especialista",
            ),
        ),
        (
            "senior",
            (
                "senior",
                "sênior",
                " sr ",
            ),
        ),
        (
            "pleno",
            (
                "pleno",
                "mid-level",
                "mid level",
                " mid ",
            ),
        ),
        (
            "junior",
            (
                "junior",
                "júnior",
                " jr ",
            ),
        ),
    )
    padded = f" {normalized} "
    for canonical, tokens in checks:
        if any(token in padded for token in tokens):
            return canonical
    return "nao_informada"


def is_known_seniority(value: str) -> bool:
    return normalize_seniority_label(value) in _CANONICAL_SENIORITIES


def extract_seniority_keywords(text: str) -> tuple[str, ...]:
    matches: list[str] = []
    for token in re.findall(r"[\wÀ-ÿ\-]+", text.lower()):
        normalized = normalize_seniority_label(token)
        if normalized != "nao_informada" and normalized not in matches:
            matches.append(normalized)
    return tuple(matches)
