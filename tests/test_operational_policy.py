import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from job_hunter_agent.core.operational_policy import (
    get_runtime_operational_policy,
    load_operational_policy,
    set_runtime_operational_policy_path,
)


class OperationalPolicyTests(TestCase):
    def setUp(self) -> None:
        self._original_runtime_path = Path("./operational_policy.json")
        set_runtime_operational_policy_path(self._original_runtime_path)

    def tearDown(self) -> None:
        set_runtime_operational_policy_path(self._original_runtime_path)

    def test_load_operational_policy_reads_valid_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "policy.json"
            path.write_text(
                json.dumps(
                    {
                        "operational_summary_order": ["pronto_para_envio", "similar_jobs"],
                        "queue_reason_rank": {"pronto_para_envio": 0, "similar_jobs": 6},
                        "queue_unknown_reason_rank": 3,
                        "queue_auto_supported_unknown_rank": 1,
                        "queue_cta_unknown_rank": 2,
                        "support_order": {"auto_supported": 0, "manual_review": 1, "unsupported": 2},
                        "priority_order": {"alta": 0, "media": 1, "baixa": 2},
                    }
                ),
                encoding="utf-8",
            )
            policy = load_operational_policy(path)

        self.assertEqual(policy.operational_summary_order, ("pronto_para_envio", "similar_jobs"))
        self.assertEqual(policy.queue_reason_rank["similar_jobs"], 6)
        self.assertEqual(policy.support_order["manual_review"], 1)

    def test_get_runtime_operational_policy_uses_runtime_path(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "policy.json"
            path.write_text(
                json.dumps(
                    {
                        "operational_summary_order": ["submitted"],
                        "queue_reason_rank": {"submitted": 0},
                        "queue_unknown_reason_rank": 3,
                        "queue_auto_supported_unknown_rank": 1,
                        "queue_cta_unknown_rank": 2,
                        "support_order": {"auto_supported": 0},
                        "priority_order": {"alta": 0},
                    }
                ),
                encoding="utf-8",
            )
            set_runtime_operational_policy_path(path)
            policy = get_runtime_operational_policy()

        self.assertEqual(policy.operational_summary_order, ("submitted",))
        self.assertEqual(policy.queue_reason_rank["submitted"], 0)
