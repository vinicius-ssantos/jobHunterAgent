from unittest import TestCase

from job_hunter_agent.core.seniority import infer_seniority_from_text, normalize_seniority_label


class SeniorityTests(TestCase):
    def test_infer_seniority_detects_pleno_aliases(self) -> None:
        self.assertEqual(infer_seniority_from_text("Pessoa Engenheira de Software Pleno"), "pleno")
        self.assertEqual(infer_seniority_from_text("Backend Engineer Mid-Level"), "pleno")

    def test_infer_seniority_detects_especialista_and_lideranca(self) -> None:
        self.assertEqual(infer_seniority_from_text("Staff Engineer"), "especialista")
        self.assertEqual(infer_seniority_from_text("Tech Lead / Head de Engenharia"), "lideranca")

    def test_normalize_seniority_label_maps_known_aliases(self) -> None:
        self.assertEqual(normalize_seniority_label("mid"), "pleno")
        self.assertEqual(normalize_seniority_label("principal"), "especialista")
        self.assertEqual(normalize_seniority_label("lead"), "lideranca")

    def test_unknown_seniority_falls_back_to_nao_informada(self) -> None:
        self.assertEqual(infer_seniority_from_text("Backend Engineer"), "nao_informada")
        self.assertEqual(normalize_seniority_label("guru"), "nao_informada")
