from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path

from job_hunter_agent.core.skill_taxonomy import get_runtime_skill_taxonomy


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


@dataclass(frozen=True)
class ExperienceAnswer:
    skill_key: str
    years: int
    question: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class CandidateProfile:
    confirmed_experience_years: dict[str, int]

    def years_for_skill(self, skill_key: str) -> int | None:
        return self.confirmed_experience_years.get(skill_key)


def load_candidate_profile(path: str | Path) -> CandidateProfile:
    profile_path = Path(path)
    if not profile_path.exists():
        return CandidateProfile(confirmed_experience_years={})
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    experience_years = payload.get("experience_years", {})
    confirmed: dict[str, int] = {}
    for raw_key, raw_value in experience_years.items():
        skill_key = normalize_skill_key(raw_key)
        if not skill_key:
            continue
        years = _extract_confirmed_years(raw_value)
        if years is None:
            continue
        confirmed[skill_key] = years
    question_entries = payload.get("questions", {})
    if isinstance(question_entries, dict):
        for raw_value in question_entries.values():
            if not isinstance(raw_value, dict):
                continue
            if raw_value.get("type") != "experience_years":
                continue
            skill_key = normalize_skill_key(str(raw_value.get("skill") or ""))
            if not skill_key:
                question_text = str(raw_value.get("question") or "")
                skill_key = extract_skill_key_from_experience_question(question_text) or ""
            if not skill_key:
                continue
            years = _extract_confirmed_years(raw_value)
            if years is None:
                continue
            confirmed[skill_key] = years
    return CandidateProfile(confirmed_experience_years=confirmed)


def record_pending_questions(path: str | Path, questions: tuple[str, ...]) -> Path:
    profile_path = Path(path)
    existing_payload = _read_profile_payload(profile_path)
    pending_payload = existing_payload.get("questions", {})
    if not isinstance(pending_payload, dict):
        pending_payload = {}

    for question in questions:
        if not question.strip():
            continue
        question_key = build_question_key(question)
        current = pending_payload.get(question_key, {})
        suggested = current.get("suggested") if isinstance(current, dict) else None
        confirmed = current.get("confirmed") if isinstance(current, dict) else None
        pending_payload[question_key] = {
            "question": question,
            "type": classify_question_type(question),
            "skill": extract_skill_key_from_experience_question(question),
            "suggested": suggested,
            "confirmed": confirmed,
        }

    existing_payload["questions"] = dict(sorted(pending_payload.items()))
    profile_path.write_text(json.dumps(existing_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return profile_path


def normalize_skill_key(value: str) -> str:
    normalized = _normalize_text(value)
    for skill_key, aliases in get_runtime_skill_taxonomy().skill_aliases.items():
        if normalized == skill_key:
            return skill_key
        if any(alias in normalized for alias in aliases):
            return skill_key
    return normalized


def build_question_key(question: str) -> str:
    normalized = _normalize_text(question)
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_") or "question"


def classify_question_type(question: str) -> str:
    if extract_skill_key_from_experience_question(question):
        return "experience_years"
    return "unknown"


def extract_supported_experience_answers(
    questions: tuple[str, ...],
    profile: CandidateProfile | None,
) -> tuple[tuple[ExperienceAnswer, ...], tuple[str, ...]]:
    if profile is None:
        return (), tuple(questions)
    answers: list[ExperienceAnswer] = []
    unresolved: list[str] = []
    for question in questions:
        skill_key = extract_skill_key_from_experience_question(question)
        if not skill_key:
            unresolved.append(question)
            continue
        years = profile.years_for_skill(skill_key)
        if years is None:
            unresolved.append(question)
            continue
        answers.append(
            ExperienceAnswer(
                skill_key=skill_key,
                years=years,
                question=question,
                aliases=get_runtime_skill_taxonomy().skill_aliases.get(skill_key, (skill_key,)),
            )
        )
    return tuple(answers), tuple(unresolved)


def extract_skill_key_from_experience_question(question: str) -> str | None:
    normalized = _normalize_text(question)
    if not normalized:
        return None
    experience_hints = (
        "ha quantos anos",
        "há quantos anos",
        "years of experience",
        "anos de experiencia",
        "anos de experiência",
        "uses",
        "usa",
    )
    if not any(hint in normalized for hint in experience_hints):
        return None
    for skill_key, aliases in get_runtime_skill_taxonomy().skill_aliases.items():
        if any(alias in normalized for alias in aliases):
            return skill_key
    return None


def _extract_confirmed_years(raw_value) -> int | None:
    if isinstance(raw_value, int):
        return raw_value
    if isinstance(raw_value, float):
        return int(raw_value)
    if isinstance(raw_value, dict):
        confirmed_value = raw_value.get("confirmed")
        if isinstance(confirmed_value, (int, float)):
            return int(confirmed_value)
    return None


def _read_profile_payload(profile_path: Path) -> dict:
    if not profile_path.exists():
        return {}
    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
