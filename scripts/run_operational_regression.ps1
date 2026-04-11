$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$tests = @(
    "tests/test_application_readiness.py",
    "tests/test_application_messages.py",
    "tests/test_application_insights.py",
    "tests/test_application_cli_rendering.py",
    "tests/test_notifier.py",
    "tests/test_linkedin_application.py",
    "tests/test_linkedin_application_review.py",
    "tests/test_linkedin_application_entry_strategies.py",
    "tests/test_linkedin_application_artifacts.py",
    "tests/test_database.py",
    "tests/test_app.py"
)

python -m pytest @tests -q
