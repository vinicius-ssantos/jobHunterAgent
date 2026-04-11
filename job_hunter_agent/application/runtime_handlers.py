from __future__ import annotations

import asyncio
import logging

from job_hunter_agent.application.application_messages import (
    format_preflight_cli_result,
    format_submit_cli_result,
)


async def handle_approved_jobs(
    application_preparation,
    job_ids: list[int],
    *,
    logger: logging.Logger,
) -> None:
    drafts = application_preparation.create_drafts_for_approved_jobs(
        job_ids,
        notes="rascunho criado apos aprovacao humana",
    )
    if drafts:
        logger.info("Pre-fase de candidatura criou %s rascunho(s) para vagas aprovadas.", len(drafts))


async def handle_application_preflight(
    application_preflight,
    application_id: int,
    *,
    logger: logging.Logger,
) -> str:
    result = await asyncio.to_thread(application_preflight.run_for_application, application_id)
    logger.info(
        "Preflight de candidatura concluido. application_id=%s outcome=%s status=%s",
        application_id,
        result.outcome,
        result.application_status,
    )
    return format_preflight_cli_result(
        detail=result.detail,
        application_status=result.application_status,
    )


async def handle_application_submit(
    application_submission,
    application_id: int,
    *,
    logger: logging.Logger,
) -> str:
    result = await asyncio.to_thread(application_submission.run_for_application, application_id)
    logger.info(
        "Submissao de candidatura concluida. application_id=%s outcome=%s status=%s",
        application_id,
        result.outcome,
        result.application_status,
    )
    return format_submit_cli_result(
        detail=result.detail,
        application_status=result.application_status,
    )
