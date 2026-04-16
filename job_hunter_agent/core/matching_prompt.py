from __future__ import annotations

from job_hunter_agent.core.domain import RawJob
from job_hunter_agent.core.matching import MatchingCriteria


def build_legacy_scoring_prompt(raw_job: RawJob, criteria: MatchingCriteria) -> str:
    return f"""
        Avalie aderencia de uma vaga ao perfil profissional abaixo.

        Perfil:
        {criteria.profile_text}

        Regras:
        - Nota de 1 a 10.
        - Considere palavras positivas: {_format_keywords(criteria.include_keywords)}
        - Considere palavras negativas: {_format_keywords(criteria.exclude_keywords)}
        - Modalidades aceitas: {_format_work_modes(criteria.accepted_work_modes)}
        - Senioridades alvo: {_format_seniorities(criteria.target_seniorities)}
        - Aceitar senioridade nao informada: {_format_bool(criteria.allow_unknown_seniority)}
        - Salario minimo em BRL: {criteria.minimum_salary_brl}
        - Seja conservador. So aprove quando a vaga realmente fizer sentido.
        - A rationale deve ser curta e ancorada em sinais objetivos da vaga.
        {build_scoring_rationale_guidance()}

        Vaga:
        titulo: {raw_job.title}
        empresa: {raw_job.company}
        local: {raw_job.location}
        modalidade: {raw_job.work_mode}
        salario: {raw_job.salary_text}
        resumo: {raw_job.summary}
        descricao: {raw_job.description}

        Retorne apenas JSON:
        {{
          "relevance": 7,
          "rationale": "stack_alinhada; modalidade_compativel"
        }}
        """


def build_scoring_rationale_guidance() -> str:
    return (
        "- Prefira tokens curtos e consistentes na rationale, como: "
        "stack_alinhada, stack_parcial, senioridade_compativel, senioridade_duvidosa, "
        "senioridade_fora_do_alvo, senioridade_nao_informada, modalidade_compativel, "
        "salario_abaixo, localizacao_duvidosa, sinais_insuficientes."
    )


def _format_keywords(values: tuple[str, ...]) -> str:
    return ", ".join(values) or "nenhuma"


def _format_work_modes(values: tuple[str, ...]) -> str:
    return ", ".join(values) or "qualquer"


def _format_seniorities(values: tuple[str, ...]) -> str:
    return ", ".join(values) or "qualquer"


def _format_bool(value: bool) -> str:
    return "sim" if value else "nao"
