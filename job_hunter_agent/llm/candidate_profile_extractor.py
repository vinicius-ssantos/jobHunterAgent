from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

from job_hunter_agent.core.browser_support import extract_json_object
from job_hunter_agent.core.candidate_profile import normalize_skill_key
from job_hunter_agent.core.skill_taxonomy import get_runtime_skill_taxonomy


@dataclass(frozen=True)
class CandidateProfileSuggestion:
    experience_years: dict[str, int]
    rationale: str = ""


def extract_resume_text(path: str | Path) -> str:
    from pypdf import PdfReader

    resume_path = Path(path)
    reader = PdfReader(str(resume_path))
    chunks: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            chunks.append(text.strip())
    return "\n\n".join(chunks).strip()


class OllamaCandidateProfileSuggester:
    def __init__(self, model_name: str, base_url: str) -> None:
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise RuntimeError(
                "Dependencias de extracao do perfil do candidato nao estao instaladas. Rode pip install -r requirements.txt."
            ) from exc
        self._llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.1)

    def suggest_from_resume_text(self, resume_text: str) -> CandidateProfileSuggestion:
        focus_stacks = ", ".join(get_runtime_skill_taxonomy().prompt_focus_stacks)
        response = self._llm.invoke(
            f"""
            Extraia sugestoes conservadoras de anos de experiencia por tecnologia a partir do curriculo.

            Regras:
            - Responda apenas JSON.
            - Seja conservador.
            - Use apenas tecnologias claramente presentes no curriculo.
            - Nunca preencha `confirmed`.
            - Retorne apenas `suggested` com numeros inteiros.
            - Foque nas stacks priorizadas do runtime atual: {focus_stacks}.

            Curriculo:
            {resume_text[:12000]}

            Retorne apenas JSON:
            {{
              "experience_years": {{
                "java": {{"suggested": 8}},
                "angular": {{"suggested": 4}}
              }},
              "rationale": "motivo curto em portugues"
            }}
            """
        )
        response_text = response.content if hasattr(response, "content") else str(response)
        return parse_candidate_profile_suggestion_response(response_text)


def parse_candidate_profile_suggestion_response(response_text: str) -> CandidateProfileSuggestion:
    payload = extract_json_object(response_text)
    if not payload:
        return CandidateProfileSuggestion(experience_years={}, rationale="resposta do modelo sem JSON valido")
    experience_years = payload.get("experience_years", {})
    normalized: dict[str, int] = {}
    if isinstance(experience_years, dict):
        for raw_key, raw_value in experience_years.items():
            skill_key = normalize_skill_key(str(raw_key))
            suggested = _coerce_suggested_years(raw_value)
            if not skill_key or suggested is None:
                continue
            normalized[skill_key] = suggested
    rationale = str(payload.get("rationale", "")).strip() or "perfil sugerido pelo modelo"
    return CandidateProfileSuggestion(experience_years=normalized, rationale=rationale)


def merge_candidate_profile_suggestions(
    *,
    output_path: str | Path,
    suggestion: CandidateProfileSuggestion,
    source_resume: str | Path,
) -> Path:
    profile_path = Path(output_path)
    existing_payload: dict = {}
    if profile_path.exists():
        try:
            existing_payload = json.loads(profile_path.read_text(encoding="utf-8"))
        except Exception:
            existing_payload = {}
    experience_payload = existing_payload.get("experience_years", {})
    if not isinstance(experience_payload, dict):
        experience_payload = {}

    for skill_key, years in suggestion.experience_years.items():
        current = experience_payload.get(skill_key, {})
        confirmed = current.get("confirmed") if isinstance(current, dict) else None
        experience_payload[skill_key] = {
            "suggested": years,
            "confirmed": confirmed,
        }

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_resume": str(Path(source_resume)),
        "rationale": suggestion.rationale,
        "experience_years": dict(sorted(experience_payload.items())),
    }
    profile_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return profile_path


def _coerce_suggested_years(raw_value: object) -> int | None:
    if isinstance(raw_value, dict):
        raw_value = raw_value.get("suggested")
    if isinstance(raw_value, (int, float)):
        years = int(raw_value)
    else:
        return None
    return max(0, min(99, years))
