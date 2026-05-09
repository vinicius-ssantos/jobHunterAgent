from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from job_hunter_agent.api.dependencies import get_repository
from job_hunter_agent.api.schemas import (
    CollectionLogSummaryResponse,
    CollectionOperationsReportResponse,
    CollectionRunSummaryResponse,
    OperationNextActionResponse,
    OperationsReportResponse,
)
from job_hunter_agent.application.collection_operations_report import build_collection_operations_report
from job_hunter_agent.application.operations_next_actions import build_operations_next_actions_from_repository
from job_hunter_agent.infrastructure.repository import JobRepository

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("/next-actions", response_model=list[OperationNextActionResponse])
def list_next_actions(
    limit: int = Query(default=20, ge=1, le=100),
    repository: JobRepository = Depends(get_repository),
) -> list[OperationNextActionResponse]:
    actions = build_operations_next_actions_from_repository(repository)
    return [OperationNextActionResponse(**action.__dict__) for action in actions[:limit]]


@router.get("/report", response_model=OperationsReportResponse)
def get_operations_report(
    days: int = Query(default=1, ge=1, le=365),
    repository: JobRepository = Depends(get_repository),
) -> OperationsReportResponse:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    report = build_collection_operations_report(repository, since=since)
    return OperationsReportResponse(
        collection=CollectionOperationsReportResponse(
            run_summary=CollectionRunSummaryResponse(**report.run_summary.__dict__),
            log_summary=CollectionLogSummaryResponse(
                by_source=report.log_summary.by_source,
                by_level=report.log_summary.by_level,
                recent_warnings_or_errors=list(report.log_summary.recent_warnings_or_errors),
            ),
        )
    )
