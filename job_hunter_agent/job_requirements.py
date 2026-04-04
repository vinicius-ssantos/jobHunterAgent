from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from job_hunter_agent.browser_support import extract_json_object
from job_hunter_agent.domain import JobPosting


@dataclass(frozen=True)
class JobRequirementSignals:
    seniority: str = "nao_informada"
    primary_stack: tuple[str, ...] = ()
    secondary_stack: tuple[str, ...] = ()
    english_level: str = "nao_informado"
    leadership_signals: bool = False
    rationale: str = ""


class JobRequirementsExtractor(Protocol):
    def extract(self, job: JobPosting) -> JobRequirementSignals:
        raise NotImplementedError


class DeterministicJobRequirementsExtractor:
    def extract(self, job: JobPosting) -> JobRequirementSignals:
        combined = f"{job.title} {job.summary}".lower()
        seniority = _infer_seniority(combined)
        primary_stack = _find_keywords(combined, ("java", "kotlin", "spring", "spring boot", "angular", "react"))
        secondary_stack = _find_keywords(
            combined,
            ("aws", "azure", "docker", "kubernetes", "postgresql", "sql", "microservices"),
        )
        english_level = _infer_english_level(combined)
        leadership_signals = any(
            token in combined
            for token in ("lideranca", "liderar", "tech lead", "mentoria", "coordenar", "ownership")
        )
        return JobRequirementSignals(
            seniority=seniority,
            primary_stack=primary_stack,
            secondary_stack=secondary_stack,
            english_level=english_level,
            leadership_signals=leadership_signals,
            rationale="sinais extraidos por heuristica local",
        )


class OllamaJobRequirementsExtractor:
    def __init__(self, model_name: str, base_url: str) -> None:
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise RuntimeError(
                "Dependencias de extracao estruturada nao estao instaladas. Rode pip install -r requirements.txt."
            ) from exc
        self._llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.1)

    def extract(self, job: JobPosting) -> JobRequirementSignals:
        response = self._llm.invoke(
            f"""
            Extraia sinais estruturados de uma vaga.

            Regras:
            - Responda apenas JSON.
            - Seja conservador.
            - Nunca invente tecnologia ou senioridade nao mencionada.
            - Campos validos:
              - seniority: junior, pleno, senior, especialista, lideranca, nao_informada
              - primary_stack: lista curta
              - secondary_stack: lista curta
              - english_level: nao_informado, basico, intermediario, avancado, fluente
              - leadership_signals: true ou false
              - rationale: motivo curto em portugues

            Vaga:
            titulo: {job.title}
            empresa: {job.company}
            resumo: {job.summary}

            Retorne apenas JSON:
            {{
              "seniority": "pleno",
              "primary_stack": ["java", "spring"],
              "secondary_stack": ["aws"],
              "english_level": "intermediario",
              "leadership_signals": false,
              "rationale": "sinais extraidos do texto"
            }}
            """
        )
        response_text = response.content if hasattr(response, "content") else str(response)
        return parse_job_requirements_response(response_text)


def parse_job_requirements_response(response_text: str) -> JobRequirementSignals:
    payload = extract_json_object(response_text)
    if not payload:
        return JobRequirementSignals(rationale="resposta do modelo sem JSON valido")

    seniority = str(payload.get("seniority", "nao_informada")).strip().lower() or "nao_informada"
    if seniority not in {"junior", "pleno", "senior", "especialista", "lideranca", "nao_informada"}:
        seniority = "nao_informada"

    english_level = str(payload.get("english_level", "nao_informado")).strip().lower() or "nao_informado"
    if english_level not in {"nao_informado", "basico", "intermediario", "avancado", "fluente"}:
        english_level = "nao_informado"

    return JobRequirementSignals(
        seniority=seniority,
        primary_stack=_normalize_stack(payload.get("primary_stack")),
        secondary_stack=_normalize_stack(payload.get("secondary_stack")),
        english_level=english_level,
        leadership_signals=bool(payload.get("leadership_signals", False)),
        rationale=str(payload.get("rationale", "")).strip() or "sinais extraidos pelo modelo",
    )


def format_job_requirement_signals(signals: JobRequirementSignals) -> str:
    primary = ", ".join(signals.primary_stack) or "-"
    secondary = ", ".join(signals.secondary_stack) or "-"
    leadership = "sim" if signals.leadership_signals else "nao"
    return (
        "sinais estruturados: "
        f"senioridade={signals.seniority}; "
        f"stack_principal={primary}; "
        f"stack_secundaria={secondary}; "
        f"ingles={signals.english_level}; "
        f"lideranca={leadership}"
    )


def extract_job_requirement_signals(notes: str) -> JobRequirementSignals:
    normalized = notes.strip()
    if "sinais estruturados:" not in normalized.lower():
        return JobRequirementSignals()

    payload = normalized.split("sinais estruturados:", 1)[1].strip().splitlines()[0]
    fields: dict[str, str] = {}
    for chunk in payload.split(";"):
        token = chunk.strip()
        if not token or "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key.strip().lower()] = value.strip()

    return JobRequirementSignals(
        seniority=fields.get("senioridade", "nao_informada") or "nao_informada",
        primary_stack=_parse_stack_field(fields.get("stack_principal", "")),
        secondary_stack=_parse_stack_field(fields.get("stack_secundaria", "")),
        english_level=fields.get("ingles", "nao_informado") or "nao_informado",
        leadership_signals=fields.get("lideranca", "nao").lower() == "sim",
        rationale="extraido das observacoes da candidatura",
    )


def format_job_requirement_summary(signals: JobRequirementSignals) -> str:
    parts: list[str] = []
    if signals.seniority != "nao_informada":
        parts.append(f"senioridade={signals.seniority}")
    if signals.primary_stack:
        parts.append(f"stack={', '.join(signals.primary_stack[:3])}")
    if signals.english_level != "nao_informado":
        parts.append(f"ingles={signals.english_level}")
    if signals.leadership_signals:
        parts.append("lideranca=sim")
    return " | ".join(parts) if parts else "nao informados"


def _infer_seniority(text: str) -> str:
    if any(token in text for token in ("tech lead", "lideranca", "lead ", "liderar")):
        return "lideranca"
    if any(token in text for token in ("especialista", "staff", "principal")):
        return "especialista"
    if "senior" in text or "sênior" in text:
        return "senior"
    if "pleno" in text or "mid-level" in text:
        return "pleno"
    if "junior" in text or "júnior" in text:
        return "junior"
    return "nao_informada"


def _infer_english_level(text: str) -> str:
    if "english fluent" in text or "ingles fluente" in text:
        return "fluente"
    if "english advanced" in text or "ingles avancado" in text:
        return "avancado"
    if "english intermediate" in text or "ingles intermediario" in text:
        return "intermediario"
    if "english basic" in text or "ingles basico" in text:
        return "basico"
    return "nao_informado"


def _find_keywords(text: str, candidates: tuple[str, ...]) -> tuple[str, ...]:
    found: list[str] = []
    for candidate in candidates:
        if candidate in text and candidate not in found:
            found.append(candidate)
    return tuple(found)


def _normalize_stack(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    normalized: list[str] = []
    for item in value:
        token = str(item).strip().lower()
        if token and token not in normalized:
            normalized.append(token)
    return tuple(normalized)


def _parse_stack_field(value: str) -> tuple[str, ...]:
    if not value or value == "-":
        return ()
    normalized: list[str] = []
    for token in value.split(","):
        item = token.strip().lower()
        if item and item not in normalized:
            normalized.append(item)
    return tuple(normalized)
