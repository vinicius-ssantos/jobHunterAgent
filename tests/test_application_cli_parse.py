from unittest import TestCase
from unittest.mock import patch

from job_hunter_agent.application.application_cli import parse_args


class ApplicationCliParseTests(TestCase):
    def test_parse_args_accepts_applications_diagnose_command(self) -> None:
        with patch("sys.argv", ["main.py", "applications", "diagnose", "--id", "32"]):
            args = parse_args()

        self.assertEqual(args.command, "applications")
        self.assertEqual(args.applications_command, "diagnose")
        self.assertEqual(args.id, 32)

    def test_parse_args_rejects_negative_cycle_interval_with_portuguese_message(self) -> None:
        with patch("sys.argv", ["main.py", "--ciclos", "2", "--intervalo-ciclos-segundos", "-1"]):
            with self.assertRaises(SystemExit) as raised:
                parse_args()

        self.assertNotEqual(raised.exception.code, 0)
