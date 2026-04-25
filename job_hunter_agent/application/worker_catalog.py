from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerDefinition:
    name: str
    cli_command: str
    module_path: str
    responsibility: str
    consumes: tuple[str, ...] = ()
    publishes: tuple[str, ...] = ()
    initializes_browser: bool = False
    initializes_telegram: bool = False
    initializes_llm: bool = False


WORKER_DEFINITIONS: tuple[WorkerDefinition, ...] = (
    WorkerDefinition(
        name="collector-worker",
        cli_command="python main.py worker collect",
        module_path="job_hunter_agent.application.collector_worker.run_collector_worker_once",
        responsibility="Coleta vagas nas fontes configuradas e publica eventos JobCollectedV1.",
        publishes=("JobCollectedV1",),
        initializes_browser=True,
        initializes_llm=True,
    ),
    WorkerDefinition(
        name="matching-worker",
        cli_command="python main.py worker match",
        module_path="job_hunter_agent.application.matching_worker.run_matching_worker_once",
        responsibility="Consome JobCollectedV1, aplica regra minima de aceite e publica JobScoredV1.",
        consumes=("JobCollectedV1",),
        publishes=("JobScoredV1",),
    ),
    WorkerDefinition(
        name="review-notifier-worker",
        cli_command="python main.py --agora",
        module_path="job_hunter_agent.application.runtime_execution.run_collection_cycle",
        responsibility="Notifica vagas para revisao humana e registra respostas operacionais.",
        consumes=("JobCollectedV1",),
        initializes_telegram=True,
    ),
    WorkerDefinition(
        name="application-worker",
        cli_command="python main.py applications preflight|submit|auto-apply",
        module_path="job_hunter_agent.application.application_submission.ApplicationSubmissionService",
        responsibility="Executa preflight, autorizacao operacional e envio assistido de candidaturas.",
        consumes=("ApplicationAuthorizedV1",),
        publishes=("ApplicationPreflightCompletedV1", "ApplicationSubmittedV1", "ApplicationBlockedV1"),
        initializes_browser=True,
        initializes_llm=True,
    ),
    WorkerDefinition(
        name="scheduler-worker",
        cli_command="python main.py",
        module_path="job_hunter_agent.application.runtime_execution.run_scheduler",
        responsibility="Agenda ciclos de coleta e coordena chamadas periodicas do runtime.",
    ),
)


def list_worker_definitions() -> tuple[WorkerDefinition, ...]:
    return WORKER_DEFINITIONS


def render_worker_catalog() -> str:
    lines = ["Workers disponiveis:"]
    for worker in WORKER_DEFINITIONS:
        lines.append(f"- {worker.name}: {worker.responsibility}")
        lines.append(f"  comando: {worker.cli_command}")
        if worker.consumes:
            lines.append(f"  consome: {', '.join(worker.consumes)}")
        if worker.publishes:
            lines.append(f"  publica: {', '.join(worker.publishes)}")
        dependencies = []
        if worker.initializes_browser:
            dependencies.append("browser")
        if worker.initializes_telegram:
            dependencies.append("telegram")
        if worker.initializes_llm:
            dependencies.append("llm")
        if dependencies:
            lines.append(f"  dependencias runtime: {', '.join(dependencies)}")
        else:
            lines.append("  dependencias runtime: nenhuma pesada esperada")
    return "\n".join(lines)
