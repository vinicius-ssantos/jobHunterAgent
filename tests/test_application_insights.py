from unittest import TestCase

from job_hunter_agent.core.application_insights import (
    classify_application_operational_insight,
    classify_operational_detail,
)
from job_hunter_agent.core.domain import JobApplication


class ApplicationOperationalInsightsTests(TestCase):
    def test_classifies_similar_jobs_as_blocked(self) -> None:
        application = JobApplication(
            id=1,
            job_id=10,
            status="error_submit",
            last_error="readiness=listing_redirect | motivo=a navegacao caiu em listagem ou colecao do LinkedIn | pagina=https://www.linkedin.com/jobs/collections/similar-jobs/",
        )

        insight = classify_application_operational_insight(application)

        self.assertEqual(insight.classification, "blocked")
        self.assertEqual(insight.reason_code, "similar_jobs")

    def test_classifies_unanswered_questions_as_manual_review(self) -> None:
        application = JobApplication(
            id=1,
            job_id=10,
            status="error_submit",
            last_error="submissao real bloqueada: fluxo nao chegou ao botao de envio | bloqueio=perguntas_obrigatorias, etapa_intermediaria | perguntas_pendentes=ha quantos anos voce usa java?",
        )

        insight = classify_application_operational_insight(application)

        self.assertEqual(insight.classification, "manual_review")
        self.assertEqual(insight.reason_code, "perguntas_adicionais")

    def test_classifies_ready_state(self) -> None:
        application = JobApplication(
            id=1,
            job_id=10,
            status="confirmed",
            last_preflight_detail="preflight real | preenchidos=email, telefone | revisao_final_alcancada=sim | pronto_para_envio=sim | ok: fluxo pronto para submissao assistida no LinkedIn",
        )

        insight = classify_application_operational_insight(application)

        self.assertEqual(insight.classification, "ready")
        self.assertEqual(insight.reason_code, "pronto_para_envio")

    def test_classify_operational_detail_handles_external_apply(self) -> None:
        insight = classify_operational_detail(
            "readiness=no_apply_cta | motivo=a vaga so oferece candidatura externa no site da empresa"
        )

        self.assertEqual(insight.classification, "blocked")
        self.assertEqual(insight.reason_code, "candidatura_externa")
