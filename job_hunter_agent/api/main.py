from __future__ import annotations

from fastapi import FastAPI

from job_hunter_agent.api.routes import applications, health, jobs, operations, status

app = FastAPI(
    title="Job Hunter Agent Admin API",
    description="Local read-only admin API for the Job Hunter Agent cockpit.",
    version="0.1.0",
)

app.include_router(health.router, prefix="/api")
app.include_router(status.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(applications.router, prefix="/api")
app.include_router(operations.router, prefix="/api")
