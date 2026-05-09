from __future__ import annotations

from fastapi import APIRouter, Depends

from job_hunter_agent.api.dependencies import get_repository
from job_hunter_agent.api.schemas import StatusOverviewResponse
from job_hunter_agent.infrastructure.repository import JobRepository

router = APIRouter(tags=["status"])


@router.get("/status", response_model=StatusOverviewResponse)
def get_status(repository: JobRepository = Depends(get_repository)) -> StatusOverviewResponse:
    return StatusOverviewResponse(
        jobs=repository.summary(),
        applications=repository.application_summary(),
    )
