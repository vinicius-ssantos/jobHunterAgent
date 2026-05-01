from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from job_hunter_agent.application.application_cli import parse_args
from job_hunter_agent.application.application_report import DEFAULT_APPLICATION_REPORTS_DIR


class ApplicationCliParseTests(TestCase):
    def test_parse_args_accepts_applications_diagnose_command(self) -> None:
        with patch("sys.argv", ["main.py", "applications", "diagnose", "--id", "32"]):
            args = parse_args()

        self.assertEqual(args.command, "applications")
        self.assertEqual(args.applications_command, "diagnose")
        self.assertEqual(args.id, 32)

    def test_parse_args_accepts_applications_report_command(self) -> None:
        with patch("sys.argv", ["main.py", "applications", "report", "--id", "32"]):
            args = parse_args()

        self.assertEqual(args.command, "applications")
        self.assertEqual(args.applications_command, "report")
        self.assertEqual(args.id, 32)
        self.assertIsNone(args.output)
        self.assertFalse(args.force)

    def test_parse_args_accepts_applications_report_output_and_force(self) -> None:
        with patch(
            "sys.argv",
            [
                "main.py",
                "applications",
                "report",
                "--id",
                "32",
                "--output",
                "custom/report.md",
                "--force",
            ],
        ):
            args = parse_args()

        self.assertEqual(args.command, "applications")
        self.assertEqual(args.applications_command, "report")
        self.assertEqual(args.id, 32)
        self.assertEqual(args.output, Path("custom/report.md"))
        self.assertTrue(args.force)

    def test_parse_args_accepts_applications_reports_list_defaults(self) -> None:
        with patch("sys.argv", ["main.py", "applications", "reports", "list"]):
            args = parse_args()

        self.assertEqual(args.command, "applications")
        self.assertEqual(args.applications_command, "reports")
        self.assertEqual(args.applications_reports_command, "list")
        self.assertEqual(args.limit, 20)
        self.assertEqual(args.dir, DEFAULT_APPLICATION_REPORTS_DIR)

    def test_parse_args_accepts_applications_reports_list_options(self) -> None:
        with patch(
            "sys.argv",
            [
                "main.py",
                "applications",
                "reports",
                "list",
                "--limit",
                "7",
                "--dir",
                "custom/reports",
            ],
        ):
            args = parse_args()

        self.assertEqual(args.applications_command, "reports")
        self.assertEqual(args.applications_reports_command, "list")
        self.assertEqual(args.limit, 7)
        self.assertEqual(args.dir, Path("custom/reports"))

    def test_parse_args_accepts_applications_reports_validate_defaults(self) -> None:
        with patch("sys.argv", ["main.py", "applications", "reports", "validate"]):
            args = parse_args()

        self.assertEqual(args.command, "applications")
        self.assertEqual(args.applications_command, "reports")
        self.assertEqual(args.applications_reports_command, "validate")
        self.assertEqual(args.dir, DEFAULT_APPLICATION_REPORTS_DIR)
        self.assertFalse(args.strict)

    def test_parse_args_accepts_applications_reports_validate_options(self) -> None:
        with patch(
            "sys.argv",
            [
                "main.py",
                "applications",
                "reports",
                "validate",
                "--dir",
                "custom/reports",
                "--strict",
            ],
        ):
            args = parse_args()

        self.assertEqual(args.applications_command, "reports")
        self.assertEqual(args.applications_reports_command, "validate")
        self.assertEqual(args.dir, Path("custom/reports"))
        self.assertTrue(args.strict)

    def test_parse_args_rejects_reports_list_non_positive_limit(self) -> None:
        with patch("sys.argv", ["main.py", "applications", "reports", "list", "--limit", "0"]):
            with self.assertRaises(SystemExit) as raised:
                parse_args()

        self.assertNotEqual(raised.exception.code, 0)

    def test_parse_args_rejects_negative_cycle_interval_with_portuguese_message(self) -> None:
        with patch("sys.argv", ["main.py", "--ciclos", "2", "--intervalo-ciclos-segundos", "-1"]):
            with self.assertRaises(SystemExit) as raised:
                parse_args()

        self.assertNotEqual(raised.exception.code, 0)
