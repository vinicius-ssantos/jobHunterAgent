from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from job_hunter_agent.application.app import JobHunterApplication
from job_hunter_agent.core.domain import VALID_APPLICATION_STATUSES, VALID_STATUSES


APPLICATION_STATUS_ALIASES = {
    "all": None,
    "ready": "authorized_submit",
    "review": "ready_for_review",
    "error": "error_submit",
}

JOB_STATUS_ALIASES = {
    "all": None,
    "pending": "collected",
    "review": "collected",
    "approved_only": "approved",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Job Hunter Agent")
    parser.add_argument("--agora", action="store_true", help="Roda um ciclo imediatamente e encerra.")
    parser.add_argument("--sem-telegram", action="store_true", help="Executa sem iniciar o Telegram.")
    parser.add_argument(
        "--ciclos",
        type=int,
        default=None,
        help="Roda um numero finito de ciclos imediatamente, sem usar o agendamento diario.",
    )
    parser.add_argument(
        "--intervalo-ciclos-segundos",
        type=int,
        default=0,
        help="Intervalo em segundos entre ciclos quando usado com --ciclos.",
    )
    parser.add_argument(
        "--bootstrap-linkedin-session",
        action="store_true",
        help="Abre o Chromium para exportar o storage_state autenticado do LinkedIn.",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status", help="Mostra um resumo operacional de vagas e candidaturas.")
    subparsers.add_parser("health", help="Mostra health checks operacionais locais.")
    jobs_parser = subparsers.add_parser("jobs", help="Operacoes de revisao de vagas.")
    jobs_subparsers = jobs_parser.add_subparsers(dest="jobs_command", required=True)

    jobs_list_parser = jobs_subparsers.add_parser("list", help="Lista vagas por status.")
    jobs_list_parser.add_argument(
        "--status",
        choices=["all", "pending", "review", "approved_only", *sorted(VALID_STATUSES)],
        default="all",
        help="Filtra por status de vaga.",
    )

    jobs_approve_parser = jobs_subparsers.add_parser("approve", help="Aprova uma vaga coletada.")
    jobs_approve_parser.add_argument("--id", type=int, required=True, help="ID da vaga.")

    jobs_reject_parser = jobs_subparsers.add_parser("reject", help="Rejeita uma vaga coletada.")
    jobs_reject_parser.add_argument("--id", type=int, required=True, help="ID da vaga.")

    jobs_show_parser = jobs_subparsers.add_parser("show", help="Mostra o detalhe de uma vaga.")
    jobs_show_parser.add_argument("--id", type=int, required=True, help="ID da vaga.")

    applications_parser = subparsers.add_parser("applications", help="Operacoes de candidaturas.")
    applications_subparsers = applications_parser.add_subparsers(dest="applications_command", required=True)

    applications_list_parser = applications_subparsers.add_parser("list", help="Lista candidaturas.")
    applications_list_parser.add_argument(
        "--status",
        choices=["all", "ready", "review", "error", *sorted(VALID_APPLICATION_STATUSES)],
        default="all",
        help="Filtra por status de candidatura.",
    )

    applications_create_parser = applications_subparsers.add_parser(
        "create",
        help="Cria um rascunho de candidatura para uma vaga aprovada.",
    )
    applications_create_parser.add_argument("--job-id", type=int, required=True, help="ID da vaga aprovada.")

    applications_show_parser = applications_subparsers.add_parser("show", help="Mostra uma candidatura.")
    applications_show_parser.add_argument("--id", type=int, required=True, help="ID da candidatura.")

    applications_events_parser = applications_subparsers.add_parser(
        "events",
        help="Lista eventos recentes de uma candidatura.",
    )
    applications_events_parser.add_argument("--id", type=int, required=True, help="ID da candidatura.")
    applications_events_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Quantidade maxima de eventos retornados.",
    )

    applications_prepare_parser = applications_subparsers.add_parser(
        "prepare",
        help="Move uma candidatura de draft para ready_for_review.",
    )
    applications_prepare_parser.add_argument("--id", type=int, required=True, help="ID da candidatura.")

    applications_confirm_parser = applications_subparsers.add_parser(
        "confirm",
        help="Confirma uma candidatura pronta para revisao.",
    )
    applications_confirm_parser.add_argument("--id", type=int, required=True, help="ID da candidatura.")

    applications_cancel_parser = applications_subparsers.add_parser(
        "cancel",
        help="Cancela uma candidatura em andamento.",
    )
    applications_cancel_parser.add_argument("--id", type=int, required=True, help="ID da candidatura.")

    applications_artifacts_parser = applications_subparsers.add_parser(
        "artifacts",
        help="Lista artefatos recentes de falha do LinkedIn.",
    )
    applications_artifacts_parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Quantidade maxima de artefatos retornados.",
    )

    applications_preflight_parser = applications_subparsers.add_parser(
        "preflight",
        help="Roda o preflight de uma candidatura confirmada.",
    )
    applications_preflight_parser.add_argument("--id", type=int, required=True, help="ID da candidatura.")
    applications_preflight_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida se o preflight poderia rodar agora, sem alterar estado nem tocar o portal.",
    )

    applications_authorize_parser = applications_subparsers.add_parser(
        "authorize",
        help="Autoriza uma candidatura confirmada para envio real.",
    )
    applications_authorize_parser.add_argument("--id", type=int, required=True, help="ID da candidatura.")

    applications_submit_parser = applications_subparsers.add_parser(
        "submit",
        help="Executa o envio real de uma candidatura autorizada.",
    )
    applications_submit_parser.add_argument("--id", type=int, required=True, help="ID da candidatura.")
    applications_submit_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida se o submit poderia rodar agora, sem alterar estado nem tocar o portal.",
    )

    applications_subparsers.add_parser(
        "auto-apply",
        help="Executa envio em lote com gates e limites de seguranca do auto easy apply.",
    )

    candidate_profile_parser = subparsers.add_parser(
        "candidate-profile",
        help="Operacoes do perfil estruturado do candidato.",
    )
    candidate_profile_subparsers = candidate_profile_parser.add_subparsers(
        dest="candidate_profile_command",
        required=True,
    )

    candidate_profile_suggest_parser = candidate_profile_subparsers.add_parser(
        "suggest",
        help="Gera sugestoes de anos de experiencia a partir do curriculo.",
    )
    candidate_profile_suggest_parser.add_argument(
        "--resume-path",
        type=Path,
        default=None,
        help="Caminho do curriculo em PDF. Usa JOB_HUNTER_RESUME_PATH por padrao.",
    )
    candidate_profile_suggest_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Arquivo de saida do perfil do candidato. Usa JOB_HUNTER_CANDIDATE_PROFILE_PATH por padrao.",
    )

    worker_parser = subparsers.add_parser(
        "worker",
        help="Executa workers isolados da fase 1 (processos separados).",
    )
    worker_subparsers = worker_parser.add_subparsers(dest="worker_command", required=True)
    worker_collect_parser = worker_subparsers.add_parser(
        "collect",
        help="Executa apenas o collector_worker e emite JobCollectedV1 em NDJSON.",
    )
    worker_collect_parser.add_argument(
        "--output",
        type=Path,
        default=Path("logs/worker-events.ndjson"),
        help="Arquivo NDJSON para eventos de coleta.",
    )
    worker_match_parser = worker_subparsers.add_parser(
        "match",
        help="Executa o matching_worker consumindo JobCollectedV1 e emitindo JobScoredV1.",
    )
    worker_match_parser.add_argument(
        "--input",
        type=Path,
        default=Path("logs/worker-events.ndjson"),
        help="Arquivo NDJSON com eventos JobCollectedV1.",
    )
    worker_match_parser.add_argument(
        "--output",
        type=Path,
        default=Path("logs/worker-scored-events.ndjson"),
        help="Arquivo NDJSON de saida para eventos JobScoredV1.",
    )
    worker_match_parser.add_argument(
        "--state",
        type=Path,
        default=Path("logs/worker-match-state.json"),
        help="Arquivo JSON de estado para idempotencia dos eventos processados.",
    )

    args = parser.parse_args()
    if args.ciclos is not None and args.ciclos <= 0:
        parser.error("--ciclos deve ser maior que zero")
    if args.intervalo_ciclos_segundos < 0:
        parser.error("--intervalo-ciclos-segundos nao pode ser negativo")
    if args.agora and args.ciclos is not None:
        parser.error("use --agora ou --ciclos, nao ambos")
    if args.command is not None and (args.agora or args.ciclos is not None):
        parser.error("comandos operacionais nao podem ser combinados com --agora ou --ciclos")
    return args


def run() -> None:
    args = parse_args()
    from job_hunter_agent.application.application_cli_dispatch import execute_cli_command

    if execute_cli_command(args):
        return
    asyncio.run(
        JobHunterApplication(enable_telegram=not args.sem_telegram).run(
            run_once=args.agora,
            fixed_cycles=args.ciclos,
            cycle_interval_seconds=args.intervalo_ciclos_segundos,
        )
    )
