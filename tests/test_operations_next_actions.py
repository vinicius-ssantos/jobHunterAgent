import unittest

from job_hunter_agent.application.operations_next_actions import (
    build_operations_next_actions,
    render_operations_next_actions,
)
from job_hunter_agent.core.domain import JobApplication, JobPosting


def _job(job_id: int, title: str = "Backend Java") -> JobPosting:
    return JobPosting(
        id=job_id,
        title=title,
        company="ACME",
        location="Brasil",
        work_mode="remoto",
        salary_text="Nao informado",
        url=f"https://example.com/{job_id}",
        source_site="LinkedIn",
        summary="Resumo",
        relevance=8,
        rationale="Boa aderencia",
        external_key=f"key-{job_id}",
        status="approved",
    )


class OperationsNextActionsTests(unittest.TestCase):
    def test_build_operations_next_actions_orders_by_conservative_priority(self) -> None:
        actions = build_operations_next_actions(
            [
                (JobApplication(id=5, job_id=50, status="draft", support_level="manual_review"), _job(50)),
                (JobApplication(id=2, job_id=20, status="authorized_submit", support_level="manual_review"), _job(20)),
                (JobApplication(id=1, job_id=10, status="error_submit", support_level="manual_review"), _job(10)),
                (JobApplication(id=3, job_id=30, status="confirmed", support_level="manual_review"), _job(30)),
                (JobApplication(id=4, job_id=40, status="ready_for_review", support_level="manual_review"), _job(40)),
                (JobApplication(id=6, job_id=60, status="submitted", support_level="manual_review"), _job(60)),
            ]
        )

        self.assertEqual([action.application_id for action in actions], [1, 2, 3, 4, 5])
        self.assertEqual(actions[0].command, "python main.py applications diagnose --id 1")
        self.assertEqual(actions[1].command, "python main.py applications submit --id 2 --dry-run")
        self.assertEqual(actions[2].command, "python main.py applications preflight --id 3 --dry-run")
        self.assertEqual(actions[3].command, "python main.py applications confirm --id 4")
        self.assertEqual(actions[4].command, "python main.py applications prepare --id 5")

    def test_render_operations_next_actions_handles_empty_list(self) -> None:
        self.assertEqual(
            render_operations_next_actions([]),
            "Nenhuma proxima acao operacional encontrada.",
        )

    def test_render_operations_next_actions_includes_reason_and_command(self) -> None:
        actions = build_operations_next_actions(
            [
                (
                    JobApplication(
                        id=7,
                        job_id=70,
                        status="confirmed",
                        support_level="manual_review",
                        last_preflight_detail="preflight real | pronto_para_envio=sim | ok",
                    ),
                    _job(70, title="Data Engineer"),
                )
            ]
        )

        rendered = render_operations_next_actions(actions)

        self.assertIn("Proximas acoes operacionais: 1", rendered)
        self.assertIn("application_id=7", rendered)
        self.assertIn("vaga=Data Engineer", rendered)
        self.assertIn("motivo=pronto_para_envio", rendered)
        self.assertIn("python main.py applications preflight --id 7 --dry-run", rendered)
