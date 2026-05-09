from __future__ import annotations

from fastapi import APIRouter, Depends

from job_hunter_agent.api.dependencies import get_settings
from job_hunter_agent.api.schemas import HealthCheckItemResponse, HealthReportResponse
from job_hunter_agent.application.application_health import build_application_health_report
from job_hunter_agent.core.settings import Settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthReportResponse)
def get_health(settings: Settings = Depends(get_settings)) -> HealthReportResponse:
    report = build_application_health_report(settings)
    return HealthReportResponse(
        ok=report.ok,
        items=[
            HealthCheckItemResponse(name=item.name, status=item.status, detail=item.detail)
            for item in report.items
        ],
    )
