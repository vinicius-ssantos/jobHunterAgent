from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
import unicodedata

from job_hunter_agent.core.skill_taxonomy import get_runtime_skill_taxonomy


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").strip().lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", normalized)


@dataclass(frozen=True)
class ExperienceAnswer:
    skill_key: str
    years: int
    question: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class KnownQuestionAnswer:
    question: str
    answer_text: str
    fragments: tuple[str, ...]


@dataclass(frozen=True)
class KnownQuestionMatch:
    question: str
    answer_text: str
    fragments: tuple[str, ...]


@dataclass(frozen=True)
class CandidateProfile:
    confirmed_experience_years: dict[str, int]
    known_question_answers: tuple[KnownQuestionAnswer, ...] = ()

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
    known_answers: list[KnownQuestionAnswer] = []
    question_entries = payload.get("questions", {})
    if isinstance(question_entries, dict):
        for raw_value in question_entries.values():
            if not isinstance(raw_value, dict):
                continue
            if raw_value.get("type") != "experience_years":
                known_answer = _build_known_answer(raw_value)
                if known_answer is not None:
                    known_answers.append(known_answer)
                continue
            skill_key = normalize_skill_key(str(raw_value.get("skill") or ""))
            if not skill_key:
                question_text = str(raw_value.get("question") or "")
                skill_key = extract_skill_key_from_experience_question(question_text) or ""
            if not skill_key:
                known_answer = _build_known_answer(raw_value)
                if known_answer is not None:
                    known_answers.append(known_answer)
                continue
            years = _extract_confirmed_years(raw_value)
            if years is None:
                known_answer = _build_known_answer(raw_value)
                if known_answer is not None:
                    known_answers.append(known_answer)
                continue
            confirmed[skill_key] = years
            known_answer = _build_known_answer(raw_value)
            if known_answer is not None:
                known_answers.append(known_answer)

    for raw_entry in payload.get("known_answers", ()) if isinstance(payload.get("known_answers"), list) else ():
        if not isinstance(raw_entry, dict):
            continue
        known_answer = _build_known_answer(raw_entry)
        if known_answer is not None:
            known_answers.append(known_answer)
    deduped_known_answers = _dedupe_known_answers(known_answers)
    return CandidateProfile(
        confirmed_experience_years=confirmed,
        known_question_answers=deduped_known_answers,
    )


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


def extract_supported_known_answers(
    questions: tuple[str, ...],
    profile: CandidateProfile | None,
) -> tuple[tuple[KnownQuestionMatch, ...], tuple[str, ...]]:
    if profile is None or not profile.known_question_answers:
        return (), tuple(questions)
    matches: list[KnownQuestionMatch] = []
    unresolved: list[str] = []
    used_questions: set[str] = set()
    for question in questions:
        normalized_question = _normalize_text(question)
        best = _find_best_known_answer(normalized_question, profile.known_question_answers)
        if best is None:
            unresolved.append(question)
            continue
        key = _normalize_text(best.question)
        if key in used_questions:
            unresolved.append(question)
            continue
        used_questions.add(key)
        matches.append(
            KnownQuestionMatch(
                question=question,
                answer_text=best.answer_text,
                fragments=best.fragments,
            )
        )
    return tuple(matches), tuple(unresolved)


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


def _build_known_answer(payload: dict) -> KnownQuestionAnswer | None:
    question_text = str(payload.get("question") or "").strip()
    if not question_text:
        return None
    confirmed = payload.get("confirmed")
    if confirmed is None:
        return None
    answer_text = str(int(confirmed) if isinstance(confirmed, float) else confirmed).strip()
    if not answer_text:
        return None
    fragments = tuple(_normalize_text(item) for item in _read_fragments(payload) if _normalize_text(item))
    return KnownQuestionAnswer(
        question=question_text,
        answer_text=answer_text,
        fragments=fragments,
    )


def _read_fragments(payload: dict) -> tuple[str, ...]:
    raw_fragments = payload.get("fragments")
    if isinstance(raw_fragments, list):
        return tuple(str(item).strip() for item in raw_fragments if str(item).strip())
    question_text = str(payload.get("question") or "").strip()
    if question_text:
        return (question_text,)
    return ()


def _dedupe_known_answers(entries: list[KnownQuestionAnswer]) -> tuple[KnownQuestionAnswer, ...]:
    grouped: dict[str, KnownQuestionAnswer] = {}
    for entry in entries:
        key = _normalize_text(entry.question)
        if not key:
            continue
        grouped[key] = entry
    return tuple(grouped[key] for key in sorted(grouped))


def _find_best_known_answer(
    normalized_question: str,
    known_answers: tuple[KnownQuestionAnswer, ...],
) -> KnownQuestionAnswer | None:
    best_score = 0.0
    best_entry: KnownQuestionAnswer | None = None
    for entry in known_answers:
        fragments = entry.fragments or (_normalize_text(entry.question),)
        for fragment in fragments:
            if not fragment:
                continue
            if fragment in normalized_question or normalized_question in fragment:
                score = 1.0
            else:
                score = _question_similarity(normalized_question, fragment)
            if score > best_score:
                best_score = score
                best_entry = entry
    if best_score < 0.6:
        return None
    return best_entry


def _question_similarity(left: str, right: str) -> float:
    left_tokens = set(token for token in re.split(r"[^a-z0-9]+", left) if token)
    right_tokens = set(token for token in re.split(r"[^a-z0-9]+", right) if token)
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    if union == 0:
        return 0.0
    return intersection / union


def _read_profile_payload(profile_path: Path) -> dict:
    if not profile_path.exists():
        return {}
    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
