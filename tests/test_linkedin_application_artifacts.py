import json
from pathlib import Path
import unittest

from job_hunter_agent.collectors.linkedin_application_artifacts import LinkedInFailureArtifactCapture
from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState
from tests.tmp_workspace import prepare_workspace_tmp_dir


class LinkedInFailureArtifactCaptureTests(unittest.TestCase):
    def test_capture_preflight_inconclusive_writes_metadata(self) -> None:
        class _Page:
            def is_closed(self):
                return False

            async def content(self):
                return "<html><body>easy apply cta sem modal</body></html>"

            async def screenshot(self, path, full_page):
                Path(path).write_bytes(b"fake-png")

        class _Job:
            id = 321
            title = "Backend Engineer"
            url = "https://www.linkedin.com/jobs/view/321/"

        tmp = prepare_workspace_tmp_dir("linkedin-artifacts-preflight-inconclusive")
        capture = LinkedInFailureArtifactCapture(enabled=True, artifacts_dir=tmp)

        import asyncio

        detail = asyncio.run(
            capture.capture(
                _Page(),
                state=LinkedInApplicationPageState(
                    easy_apply=True,
                    modal_open=False,
                    cta_text="easy apply",
                    sample="easy apply | vaga",
                ),
                job=_Job(),
                phase="preflight",
                detail="preflight real inconclusivo: CTA de candidatura simplificada encontrado, mas modal nao abriu",
            )
        )

        self.assertIn("artefatos=", detail)
        meta_files = list(Path(tmp).glob("*_meta.json"))
        self.assertEqual(len(meta_files), 1)
        payload = json.loads(meta_files[0].read_text(encoding="utf-8"))
        self.assertEqual(payload["artifact_type"], "preflight")
        self.assertIn("modal nao abriu", payload["detail"])
        self.assertTrue(payload["files"]["html"].endswith("_dom.html"))

    def test_capture_writes_html_and_metadata(self) -> None:
        class _Page:
            def is_closed(self):
                return False

            async def content(self):
                return "<html><body>teste</body></html>"

            async def screenshot(self, path, full_page):
                Path(path).write_bytes(b"fake-png")

        class _Job:
            id = 999
            title = "Backend Engineer"
            url = "https://www.linkedin.com/jobs/view/999/"

        tmp = prepare_workspace_tmp_dir("linkedin-artifacts-service")
        capture = LinkedInFailureArtifactCapture(enabled=True, artifacts_dir=tmp)

        import asyncio

        detail = asyncio.run(
            capture.capture(
                _Page(),
                state=LinkedInApplicationPageState(
                    easy_apply=True,
                    modal_open=False,
                    cta_text="candidatura simplificada",
                ),
                job=_Job(),
                phase="submit",
                detail="falha de teste",
            )
        )

        files = list(Path(tmp).iterdir())
        self.assertTrue(any(path.suffix == ".html" for path in files))
        self.assertTrue(any(path.suffix == ".json" for path in files))
        self.assertTrue(any(path.suffix == ".png" for path in files))
        self.assertIn("artefatos=", detail)

    def test_build_submit_exception_result_reports_closed_page_with_artifact_metadata(self) -> None:
        class _ClosedPage:
            def is_closed(self):
                return True

            async def content(self):
                raise RuntimeError("Target page, context or browser has been closed")

            async def screenshot(self, path, full_page):
                raise RuntimeError("Target page, context or browser has been closed")

        class _Job:
            id = 654
            title = "Backend Engineer"
            url = "https://www.linkedin.com/jobs/view/654/"

        tmp = prepare_workspace_tmp_dir("linkedin-artifacts-service-closed")
        capture = LinkedInFailureArtifactCapture(enabled=True, artifacts_dir=tmp)

        import asyncio

        result = asyncio.run(
            capture.build_submit_exception_result(
                RuntimeError("Page.evaluate: Target page, context or browser has been closed"),
                page=_ClosedPage(),
                state=LinkedInApplicationPageState(modal_open=True),
                job=_Job(),
            )
        )

        self.assertEqual(result.status, "error_submit")
        self.assertIn("pagina do LinkedIn foi fechada", result.detail)
        self.assertIn("artefatos=", result.detail)
        meta_files = list(Path(tmp).glob("*_meta.json"))
        self.assertEqual(len(meta_files), 1)
        payload = json.loads(meta_files[0].read_text(encoding="utf-8"))
        self.assertTrue(payload["page_closed"])
