from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from job_hunter_agent.application.runtime_handlers import (
    handle_application_preflight,
    handle_application_submit,
    handle_approved_jobs,
)


class RuntimeHandlersTests(IsolatedAsyncioTestCase):
    async def test_handle_approved_jobs_creates_drafts_for_approved_jobs(self) -> None:
        class _PreparationService:
            def __init__(self) -> None:
                self.calls: list[tuple[list[int], str]] = []

            def create_drafts_for_approved_jobs(self, job_ids: list[int], notes: str = ""):
                self.calls.append((job_ids, notes))
                return [object()]

        logger = type("Logger", (), {"info": lambda *args, **kwargs: None})()
        service = _PreparationService()

        await handle_approved_jobs(service, [1, 2], logger=logger)

        self.assertEqual(
            service.calls,
            [([1, 2], "rascunho criado apos aprovacao humana")],
        )

    async def test_handle_application_preflight_formats_reply(self) -> None:
        class _PreflightService:
            def run_for_application(self, application_id: int):
                return type(
                    "Result",
                    (),
                    {
                        "outcome": "ready",
                        "detail": "preflight ok",
                        "application_status": "confirmed",
                    },
                )

        logger = type("Logger", (), {"info": lambda *args, **kwargs: None})()

        reply = await handle_application_preflight(_PreflightService(), 42, logger=logger)

        self.assertEqual(reply, "Preflight: preflight ok (status=confirmed)")

    async def test_handle_application_submit_formats_reply(self) -> None:
        class _SubmissionService:
            def run_for_application(self, application_id: int):
                return type(
                    "Result",
                    (),
                    {
                        "outcome": "submitted",
                        "detail": "submissao real concluida",
                        "application_status": "submitted",
                    },
                )

        logger = type("Logger", (), {"info": lambda *args, **kwargs: None})()

        reply = await handle_application_submit(_SubmissionService(), 42, logger=logger)

        self.assertEqual(reply, "Submissao: submissao real concluida (status=submitted)")

    async def test_handle_application_preflight_uses_asyncio_to_thread(self) -> None:
        class _PreflightService:
            def run_for_application(self, application_id: int):
                return type(
                    "Result",
                    (),
                    {
                        "outcome": "ready",
                        "detail": "preflight ok",
                        "application_status": "confirmed",
                    },
                )

        logger = type("Logger", (), {"info": lambda *args, **kwargs: None})()

        async def fake_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("job_hunter_agent.application.runtime_handlers.asyncio.to_thread", side_effect=fake_to_thread) as to_thread_mock:
            reply = await handle_application_preflight(_PreflightService(), 7, logger=logger)

        to_thread_mock.assert_called_once()
        self.assertEqual(reply, "Preflight: preflight ok (status=confirmed)")
