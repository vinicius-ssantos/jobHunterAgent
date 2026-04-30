from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_APPLICATION_REPORTS_DIR = Path("artifacts/reports")


class ApplicationReportAlreadyExistsError(Exception):
    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(str(path))


@dataclass(frozen=True)
class ApplicationReportArtifacts:
    report_path: Path
    manifest_path: Path


def build_application_report_path(application_id: int, *, reports_dir: Path = DEFAULT_APPLICATION_REPORTS_DIR) -> Path:
    return reports_dir / f"application-{application_id}.md"


def build_application_report_manifest_path(
    application_id: int,
    *,
    reports_dir: Path = DEFAULT_APPLICATION_REPORTS_DIR,
) -> Path:
    return reports_dir / f"application-{application_id}.json"


def build_application_report_manifest_path_for_report(report_path: Path) -> Path:
    return report_path.with_suffix(".json")


def write_application_report(
    *,
    application: object,
    job: object,
    events: list[object],
    reports_dir: Path = DEFAULT_APPLICATION_REPORTS_DIR,
    output_path: Path | None = None,
    force: bool = False,
) -> ApplicationReportArtifacts:
    report_path = output_path or build_application_report_path(application.id, reports_dir=reports_dir)
    manifest_path = (
        build_application_report_manifest_path_for_report(report_path)
        if output_path is not None
        else build_application_report_manifest_path(application.id, reports_dir=reports_dir)
    )
    for path in (report_path, manifest_path):
        if path.exists() and not force:
            raise ApplicationReportAlreadyExistsError(path)

    generated_at_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_application_evaluation_report(
            application=application,
            job=job,
            events=events,
            generated_at_utc=generated_at_utc,
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            build_application_report_manifest(
                application=application,
                job=job,
                report_path=report_path,
                manifest_path=manifest_path,
                generated_at_utc=generated_at_utc,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return ApplicationReportArtifacts(report_path=report_path, manifest_path=manifest_path)


def build_application_report_manifest(
    *,
    application: object,
    job: object,
    report_path: Path,
    manifest_path: Path,
    generated_at_utc: str,
) -> dict[str, Any]:
    return {
        "application": {
            "id": getattr(application, "id", None),
            "job_id": getattr(application, "job_id", None),
            "status": _raw_value(getattr(application, "status", None)),
        },
        "generated_at_utc": generated_at_utc,
        "job": {
            "id": getattr(job, "id", None),
            "title": _raw_value(getattr(job, "title", None)),
            "company": _raw_value(getattr(job, "company", None)),
            "source_site": _raw_value(getattr(job, "source_site", None)),
            "url": _raw_value(getattr(job, "url", None)),
            "status": _raw_value(getattr(job, "status", None)),
        },
        "manifest_path": str(manifest_path),
        "report_path": str(report_path),
        "safety": {
            "changes_status": False,
            "read_only": True,
            "runs_preflight": False,
            "runs_submit": False,
            "uses_llm": False,
        },
        "status": {
            "application": _raw_value(getattr(application, "status", None)),
            "job": _raw_value(getattr(job, "status", None)),
        },
        "support": {
            "level": _raw_value(getattr(application, "support_level", None)),
            "rationale": _raw_value(getattr(application, "support_rationale", None)),
        },
    }


def render_application_evaluation_report(
    *,
    application: object,
    job: object,
    events: list[object],
    generated_at_utc: str | None = None,
) -> str:
    generated_at = generated_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    recent_events = _render_recent_events(events)
    return "\n".join(
        [
            f"# Relatorio Da Candidatura {application.id}",
            "",
            "## Metadados",
            "",
            f"- Candidatura: {application.id}",
            f"- Vaga: {job.id}",
            f"- Empresa: {_value(job.company)}",
            f"- Titulo: {_value(job.title)}",
            f"- Status da candidatura: {_value(application.status)}",
            f"- Status da vaga: {_value(job.status)}",
            f"- Suporte operacional: {_value(application.support_level)}",
            f"- Gerado em: {generated_at}",
            "",
            "## A. Resumo Da Vaga",
            "",
            f"- Empresa: {_value(job.company)}",
            f"- Titulo: {_value(job.title)}",
            f"- Localidade: {_value(job.location)}",
            f"- Modalidade: {_value(job.work_mode)}",
            f"- Fonte: {_value(job.source_site)}",
            f"- Link: {_value(job.url)}",
            f"- Resumo: {_value(job.summary)}",
            "",
            "## B. Match Com O Perfil",
            "",
            f"- Relevancia persistida: {_value(job.relevance)}",
            f"- Rationale persistida: {_value(job.rationale)}",
            f"- Salario informado: {_value(job.salary_text)}",
            "- Observacao: este relatorio usa apenas dados ja persistidos; nao executa LLM.",
            "",
            "## C. Nivel, Estrategia E Posicionamento",
            "",
            f"- Status atual da candidatura: {_value(application.status)}",
            f"- Notas operacionais: {_value(application.notes)}",
            f"- Recomendacao deterministica: {_recommendation(application)}",
            "",
            "## D. Compensacao, Demanda E Sinais Operacionais",
            "",
            f"- Salario: {_value(job.salary_text)}",
            f"- Suporte operacional: {_value(application.support_level)}",
            f"- Rationale de suporte: {_value(application.support_rationale)}",
            f"- Ultimo preflight: {_value(application.last_preflight_detail)}",
            f"- Ultimo submit: {_value(application.last_submit_detail)}",
            f"- Ultimo erro: {_value(application.last_error)}",
            f"- Submitted at: {_value(application.submitted_at)}",
            "",
            "## E. Plano De Personalizacao",
            "",
            "- Revisar titulo, empresa, stack, senioridade e modalidade antes de gerar qualquer artefato externo.",
            "- Usar rationale persistida como sinal inicial, nao como verdade final.",
            "- Nao inventar metricas, experiencias, certificacoes ou senioridade.",
            "- Dados faltantes devem ser marcados para revisao humana.",
            "",
            "## F. Plano De Entrevista",
            "",
            "- Preparar historias alinhadas aos requisitos explicitamente presentes na vaga.",
            "- Validar gaps tecnicos antes de entrevista.",
            "- Preparar perguntas sobre escopo, time, processo, modalidade e expectativas de entrega.",
            "",
            "## Incertezas E Revisao Humana",
            "",
            "- Relatorio gerado sem LLM e sem consulta externa.",
            "- Relatorio nao altera status da candidatura.",
            "- Relatorio nao executa preflight nem submit.",
            "- Relatorio nao autoriza envio real.",
            "",
            "## Eventos Recentes Da Candidatura",
            "",
            recent_events,
            "",
        ]
    )


def _recommendation(application: object) -> str:
    status = getattr(application, "status", "")
    if status == "draft":
        return "review — preparar candidatura antes de qualquer acao externa."
    if status == "ready_for_review":
        return "review — confirmar ou cancelar apos revisao humana."
    if status == "confirmed":
        return "review — rodar preflight antes de autorizar submit."
    if status == "authorized_submit":
        return "apply — submit pode ser considerado, mantendo gate humano e dry-run quando necessario."
    if status == "submitted":
        return "hold — candidatura ja enviada."
    if status == "error_submit":
        return "hold — investigar erro antes de nova tentativa."
    if status == "cancelled":
        return "skip — candidatura cancelada."
    return "review — estado nao reconhecido."


def _render_recent_events(events: list[object]) -> str:
    if not events:
        return "- nenhum"
    return "\n".join(
        f"- {_value(event.created_at)} | {_value(event.event_type)} | "
        f"{_value(event.from_status)} -> {_value(event.to_status)} | {_value(event.detail)}"
        for event in events
    )


def _value(value: object) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    return text if text else "-"


def _raw_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
