from __future__ import annotations

from fastapi.testclient import TestClient

from job_hunter_agent.api.dependencies import get_repository, get_settings
from job_hunter_agent.api.main import app
from job_hunter_agent.core.domain import JobPosting
from job_hunter_agent.core.settings import Settings
from job_hunter_agent.infrastructure.repository import SqliteJobRepository


def _make_client(repository: SqliteJobRepository, settings: Settings) -> TestClient:
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def _clear_overrides() -> None:
    app.dependency_overrides.clear()


def _sample_job() -> JobPosting:
    return JobPosting(
        title="Backend Developer",
        company="Acme",
        location="Remoto",
        work_mode="remoto",
        salary_text="",
        url="https://example.com/jobs/1",
        source_site="LinkedIn",
        summary="Vaga backend Java.",
        relevance=8,
        rationale="Boa aderencia ao perfil.",
        external_key="linkedin:1",
    )


def test_status_endpoint_uses_isolated_repository(tmp_path):
    repository = SqliteJobRepository(tmp_path / "jobs.db")
    settings = Settings(database_path=tmp_path / "jobs.db", resume_path=tmp_path / "cv.pdf")
    client = _make_client(repository, settings)
    try:
        response = client.get("/api/status")
    finally:
        _clear_overrides()
    assert response.status_code == 200
    payload = response.json()
    assert payload["jobs"]["total"] == 0
    assert payload["applications"]["total"] == 0


def test_jobs_list_and_detail(tmp_path):
    repository = SqliteJobRepository(tmp_path / "jobs.db")
    settings = Settings(database_path=tmp_path / "jobs.db", resume_path=tmp_path / "cv.pdf")
    saved = repository.save_new_jobs([_sample_job()])
    job_id = saved[0].id
    client = _make_client(repository, settings)
    try:
        list_response = client.get("/api/jobs")
        detail_response = client.get(f"/api/jobs/{job_id}")
        missing_response = client.get("/api/jobs/999")
    finally:
        _clear_overrides()
    assert list_response.status_code == 200
    assert list_response.json()[0]["title"] == "Backend Developer"
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == job_id
    assert detail["events"][0]["event_type"] == "job_collected"
    assert missing_response.status_code == 404


def test_applications_list_detail_events_and_next_actions(tmp_path):
    repository = SqliteJobRepository(tmp_path / "jobs.db")
    settings = Settings(database_path=tmp_path / "jobs.db", resume_path=tmp_path / "cv.pdf")
    job = repository.save_new_jobs([_sample_job()])[0]
    repository.mark_status(job.id, "approved", detail="aprovada no teste")
    application = repository.create_application_draft(job.id, notes="teste")
    client = _make_client(repository, settings)
    try:
        list_response = client.get("/api/applications")
        detail_response = client.get(f"/api/applications/{application.id}")
        events_response = client.get(f"/api/applications/{application.id}/events")
        actions_response = client.get("/api/operations/next-actions")
        missing_response = client.get("/api/applications/999")
    finally:
        _clear_overrides()
    assert list_response.status_code == 200
    assert list_response.json()[0]["job"]["title"] == "Backend Developer"
    assert detail_response.status_code == 200
    assert detail_response.json()["events"][0]["event_type"] == "draft_created"
    assert events_response.status_code == 200
    assert events_response.json()[0]["application_id"] == application.id
    assert actions_response.status_code == 200
    assert actions_response.json()[0]["application_id"] == application.id
    assert missing_response.status_code == 404


def test_admin_api_does_not_expose_real_preflight_or_submit_routes(tmp_path):
    repository = SqliteJobRepository(tmp_path / "jobs.db")
    settings = Settings(database_path=tmp_path / "jobs.db", resume_path=tmp_path / "cv.pdf")
    client = _make_client(repository, settings)
    try:
        openapi_paths = set(client.get("/openapi.json").json()["paths"])
        preflight_response = client.post("/api/applications/1/preflight")
        submit_response = client.post("/api/applications/1/submit")
    finally:
        _clear_overrides()

    assert not any("preflight" in path for path in openapi_paths)
    assert not any("submit" in path for path in openapi_paths)
    assert preflight_response.status_code == 404
    assert submit_response.status_code == 404
